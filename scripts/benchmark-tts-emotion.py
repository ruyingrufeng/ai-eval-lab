#!/usr/bin/env python3
"""TTS 4 维度评测：感情/停顿/语速控制/自然度。
测试候选：MiniMax-TTS / ChatTTS / Fish Speech / edge-tts / Qwen3-TTS CustomVoice。

4 个测试用例（覆盖杰哥 4 场景）：
  T1 讲解视频：客观陈述，感情平淡
  T2 播客：主持人 + 嘉宾对话，感情丰富
  T3 有声书：叙事段落，停顿重要
  T4 数字人配音：情感语音（悲伤/欢快）+ 多语速

每个候选 × 每个用例输出 wav + 元数据 JSON。

输出目录：results/tts_emotion_bench_20260816/
"""
from __future__ import annotations
import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from datetime import datetime


# 测试用例设计：覆盖感情/停顿/语速/自然度 4 维度
TEST_CASES = {
    "T1_video_narration": {
        "scenario": "讲解视频配音",
        "text": "今天我们来讲一个关于爱情的故事。从前，有一对情侣，在雨季的咖啡馆相遇。男生点了一杯拿铁，女生要了一杯卡布奇诺。两杯咖啡的热气在空气中缠绕，像极了两颗心的靠近。",
        "expect": "中性、清晰、慢节奏、停顿分明",
    },
    "T2_podcast_dialog": {
        "scenario": "播客对话",
        "text": "主持人：欢迎来到今天的节目，我们请到了一位特别的嘉宾。嘉宾：谢谢邀请，我其实有点紧张。主持人：完全不用紧张，我们就像朋友聊天一样。对了，听说你最近在做播客？",
        "expect": "对话感、两人音色切换（做不到的部分用单声音色带节奏区分）、感情丰富",
    },
    "T3_audiobook": {
        "scenario": "有声电子书朗读",
        "text": "她站在窗前，望着远方的山峦。山顶的雪已经化了一半，露出灰褐色的岩石。她想起了十年前的那个冬天，母亲站在同一个位置对她说：去吧，外面的世界很大，不要回头。",
        "expect": "叙事感、慢语速、段落停顿（句号处）、情感低沉",
    },
    "T4_digital_human": {
        "scenario": "数字人配音（情感语音 + 多语速）",
        "text": "哈哈哈哈，今天真是太开心了！终于完成了这个大项目，感觉整个世界都亮了！不过呢，还是有一点点小小的遗憾——希望下次能做得更好。",
        "expect": "笑声、情绪起伏（喜→慎）、语速变化、语气自然",
    },
}


def probe_duration(audio_path: Path) -> float | None:
    """WAV/MP3 通用：取 wav 头或 ffprobe"""
    try:
        with wave.open(str(audio_path), "rb") as w:
            return round(w.getnframes() / w.getframerate(), 3)
    except Exception:
        pass
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, timeout=10
    )
    if r.stdout.strip():
        try:
            return round(float(r.stdout.strip()), 3)
        except ValueError:
            return None
    return None


# ---------- 各候选的合成函数 ----------
def synth_minimax(case_id: str, text: str, voice: str, speed: float, out_dir: Path) -> dict:
    """MiniMax-TTS via mmx CLI。"""
    out_path = out_dir / f"minimax_{case_id}.mp3"
    started = time.monotonic()
    try:
        r = subprocess.run([
            "mmx", "speech", "synthesize",
            "--text", text,
            "--voice", voice,
            "--speed", str(speed),
            "--format", "mp3",
            "--out", str(out_path),
            "--non-interactive",
        ], capture_output=True, text=True, timeout=120)
        elapsed = time.monotonic() - started
        if r.returncode != 0:
            return {"error": f"rc={r.returncode} stderr={r.stderr[-200:]}", "elapsed_s": elapsed}
        # mmx 输出 JSON 元数据
        meta = {}
        for line in r.stdout.strip().splitlines():
            if line.strip().startswith("{"):
                try:
                    meta = json.loads(line)
                except Exception:
                    pass
        dur = probe_duration(out_path)
        return {
            "ok": True, "elapsed_s": elapsed,
            "audio_file": str(out_path), "duration_s": dur,
            "engine": "minimax", "voice": voice, "speed": speed,
            "metadata": meta,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout 120s", "elapsed_s": time.monotonic() - started}


def synth_chattts(case_id: str, text: str, voice_seed: int, speed: float, out_dir: Path) -> dict:
    """ChatTTS via chattts_generate.py（带 [break] [oral] 标记）。"""
    out_path = out_dir / f"chattts_{case_id}.wav"
    script = "/Users/jacky/voice-tools/chattts_generate.py"
    started = time.monotonic()
    try:
        r = subprocess.run([
            "/Users/jacky/voice-tools/venv/bin/python",
            script, text,
            "-o", str(out_path),
            "--seed", str(voice_seed),
            "--speed", str(speed),
            "--temperature", "0.3",
        ], capture_output=True, text=True, timeout=300)
        elapsed = time.monotonic() - started
        if r.returncode != 0:
            return {"error": f"rc={r.returncode} stderr={r.stderr[-200:]}", "elapsed_s": elapsed}
        dur = probe_duration(out_path)
        return {
            "ok": True, "elapsed_s": elapsed,
            "audio_file": str(out_path), "duration_s": dur,
            "engine": "chattts", "voice_seed": voice_seed, "speed": speed,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout 300s", "elapsed_s": time.monotonic() - started}


def synth_edge(case_id: str, text: str, voice: str, speed: float, out_dir: Path) -> dict:
    """edge-tts via 9882 HTTP API。"""
    out_path = out_dir / f"edge_{case_id}.mp3"
    started = time.monotonic()
    try:
        import urllib.request
        body = json.dumps({
            "input": text, "voice": "default",
            "response_format": "mp3", "speed": speed,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:9882/v1/audio/speech",
            data=body, headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out_path.write_bytes(r.read())
        elapsed = time.monotonic() - started
        dur = probe_duration(out_path)
        return {
            "ok": True, "elapsed_s": elapsed,
            "audio_file": str(out_path), "duration_s": dur,
            "engine": "edge-tts", "voice": voice, "speed": speed,
        }
    except Exception as e:
        return {"error": str(e), "elapsed_s": time.monotonic() - started}


def synth_qwen(case_id: str, text: str, voice: str, speed: float, out_dir: Path) -> dict:
    """Qwen3-TTS CustomVoice via 9881。"""
    out_path = out_dir / f"qwen_{case_id}.wav"
    started = time.monotonic()
    try:
        import urllib.request
        body = json.dumps({
            "input": text, "voice": voice,
            "response_format": "wav", "speed": speed,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:9881/v1/audio/speech",
            data=body, headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 429 重试
        last_err = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    out_path.write_bytes(r.read())
                last_err = None
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(5 * (1.5 ** attempt))
                    last_err = f"429 try {attempt+1}"
                    continue
                last_err = f"HTTP {e.code}: {e.reason}"
                break
        if last_err:
            return {"error": last_err, "elapsed_s": time.monotonic() - started}
        elapsed = time.monotonic() - started
        dur = probe_duration(out_path)
        return {
            "ok": True, "elapsed_s": elapsed,
            "audio_file": str(out_path), "duration_s": dur,
            "engine": "qwen3-tts", "voice": voice, "speed": speed,
        }
    except Exception as e:
        return {"error": str(e), "elapsed_s": time.monotonic() - started}


def synth_fish(case_id: str, text: str, voice: str, speed: float, out_dir: Path) -> dict:
    """Fish Speech via tools.api_client（占位）。"""
    out_path = out_dir / f"fish_{case_id}.wav"
    return {
        "engine": "fish-speech",
        "error": "Fish Speech 装机中（依赖 pip install 跑中），本轮不跑",
        "audio_file": None,
    }


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audio-dir", type=Path, default=None)
    ap.add_argument("--cases", nargs="*", default=None,
                    help="只跑指定 case，默认全跑")
    ap.add_argument("--engines", nargs="*", default=None,
                    help="只跑指定 engine")
    args = ap.parse_args()
    out_dir = args.audio_dir or args.output.parent / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    out = {
        "schema_version": 4,
        "suite": "tts-emotion-bench",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dimensions": ["emotion", "pause", "speed", "naturalness"],
        "test_cases": TEST_CASES,
        "engines": {},
    }

    # 默认引擎清单
    ENGINES = {
        "minimax": lambda cid, t, v, s: synth_minimax(cid, t, v, s, out_dir),
        "chattts": lambda cid, t, v, s: synth_chattts(cid, t, v, s, out_dir),
        "edge-tts": lambda cid, t, v, s: synth_edge(cid, t, v, s, out_dir),
        "qwen3-tts": lambda cid, t, v, s: synth_qwen(cid, t, v, s, out_dir),
        "fish-speech": lambda cid, t, v, s: synth_fish(cid, t, v, s, out_dir),
    }
    # 默认声音/参数
    DEFAULT_VOICES = {
        "minimax": "Chinese (Mandarin)_News_Anchor",
        "chattts": 42,  # seed
        "edge-tts": "default",
        "qwen3-tts": "vivian",
        "fish-speech": "default",
    }
    DEFAULT_SPEED = {
        "minimax": 1.0,
        "chattts": 1.0,
        "edge-tts": 1.0,
        "qwen3-tts": 1.0,
        "fish-speech": 1.0,
    }

    cases = args.cases or list(TEST_CASES.keys())
    engines = args.engines or list(ENGINES.keys())

    for engine_name in engines:
        if engine_name not in ENGINES:
            print(f"[skip] unknown engine: {engine_name}")
            continue
        out["engines"][engine_name] = {"voice": DEFAULT_VOICES[engine_name],
                                       "speed": DEFAULT_SPEED[engine_name], "results": {}}
        for case_id in cases:
            tc = TEST_CASES[case_id]
            print(f"[{engine_name}] {case_id} ...", flush=True)
            t0 = time.monotonic()
            r = ENGINES[engine_name](
                case_id, tc["text"],
                DEFAULT_VOICES[engine_name], DEFAULT_SPEED[engine_name],
            )
            r["wall_s"] = round(time.monotonic() - t0, 2)
            r["scenario"] = tc["scenario"]
            r["expect"] = tc["expect"]
            r["text"] = tc["text"]
            out["engines"][engine_name]["results"][case_id] = r
            # 立即落盘（防止中断）
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            status = "OK" if r.get("ok") else f"FAIL ({r.get('error', '')[:50]})"
            print(f"  → {status} {r['wall_s']}s dur={r.get('duration_s', '-')}",
                  flush=True)

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"\nDONE: {sum(len(e['results']) for e in out['engines'].values())} samples",
          flush=True)


if __name__ == "__main__":
    main()