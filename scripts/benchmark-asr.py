#!/usr/bin/env python3
"""ASR 统一基准：faster-whisper base（CPU int8）。
矩阵：
  D 中文 CER — A1 五段已知文本（TTS 生成）→ 转写 → CER
  E 英文 WER — aiden 合成的英文 50 字 → 转写 → WER
  F 自动检测 — 不指定 language → 看自动检测的命中率
  G 长音频漂移 — 长文（~60s）→ 看尾段识别
辅助：CER/WER 用纯字符级编辑距离（去掉空格/标点）。
输出 JSON。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PYTHON = "/Users/jacky/voice-tools/venv/bin/python"
HF_ENDPOINT = "https://hf-mirror.com"
HF_CACHE = "/Users/jacky/voice-tools/models"

# 去掉标点/空白，便于中文字符级比较
_PUNCT = " \t\r\n，。！？、；：\"'()（）【】《》·.,!?;:\"'()[]<>-—…"


def norm_zh(text: str) -> str:
    """中文字符级归一化：去标点/空白/繁简（用 OpenCC 不在本机，先只去标点+小写化）。"""
    return "".join(c for c in text if c not in _PUNCT and not c.isspace()).lower()


def levenshtein(a: str, b: str) -> int:
    """O(len(a)*len(b)) 编辑距离。"""
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> dict[str, Any]:
    rn, hn = norm_zh(ref), norm_zh(hyp)
    if not rn:
        return {"ref_chars": 0, "hyp_chars": len(hn), "edits": len(hn), "cer": 1.0}
    edits = levenshtein(rn, hn)
    return {"ref_chars": len(rn), "hyp_chars": len(hn), "edits": edits,
            "cer": round(edits / len(rn), 4)}


def wer_en(ref: str, hyp: str) -> dict[str, Any]:
    rw = ref.split()
    hw = hyp.split()
    if not rw:
        return {"ref_words": 0, "edits": len(hw), "wer": 1.0}
    edits = levenshtein(" ".join(rw), " ".join(hw))  # 词级编辑距离近似
    return {"ref_words": len(rw), "hyp_words": len(hw), "edits": edits,
            "wer": round(edits / len(rw), 4)}


def transcribe(audio: Path, language: str | None, beam_size: int = 5) -> dict[str, Any]:
    """跑 faster-whisper 转写，返回 {text, segments, duration, elapsed, language_detected}。"""
    code = f"""
import sys, json, time
from faster_whisper import WhisperModel
m = WhisperModel('base', device='cpu', compute_type='int8')
t0 = time.monotonic()
segments, info = m.transcribe(sys.argv[1], language={language!r}, beam_size={beam_size})
dur = info.duration
tt = time.monotonic() - t0
out = []
for s in segments:
    out.append({{'start': round(s.start,2), 'end': round(s.end,2), 'text': s.text}})
print(json.dumps({{'language': info.language, 'language_probability': round(info.language_probability, 3),
                    'duration': round(dur,2), 'elapsed': round(tt,3), 'rtf': round(tt/dur, 3) if dur else None,
                    'text': ''.join(s.text for s in segments), 'segments': out}}))
"""
    env = {**os.environ, "HF_ENDPOINT": HF_ENDPOINT, "HF_HUB_CACHE": HF_CACHE,
           "NO_PROXY": "*", "no_proxy": "*"}
    env.pop("HTTP_PROXY", None); env.pop("HTTPS_PROXY", None)
    env.pop("http_proxy", None); env.pop("https_proxy", None)
    r = subprocess.run([PYTHON, "-c", code, str(audio)],
                       capture_output=True, text=True, timeout=600, env=env)
    if r.returncode != 0:
        return {"error": r.stderr[-400:], "audio": str(audio)}
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts-json", type=Path, required=True,
                    help="TTS benchmark JSON，含已知文本与 wav 路径")
    ap.add_argument("--audio-dir", type=Path, required=True,
                    help="TTS 输出 wav 目录")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    tts = json.loads(args.tts_json.read_text(encoding="utf-8"))

    out: dict[str, Any] = {
        "schema_version": 1,
        "suite": "asr-benchmark",
        "engine": "faster-whisper",
        "model": "base",
        "device": "cpu",
        "compute_type": "int8",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "results": {},
    }

    def emit(section: str, item: dict[str, Any]) -> None:
        out["results"].setdefault(section, []).append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{section}/{item['label']}: "
              + (f"CER={item.get('cer','-')} WER={item.get('wer','-')} "
                 f"lang={item.get('language_detected','-')} "
                 f"rtf={item.get('rtf','-')}" if not item.get('error')
                 else f"ERROR: {item['error'][:100]}"),
              flush=True)

    # ---- D 中文 CER：A1 五段已知文本 ----
    for item in tts["results"]["A_length_scaling"]:
        wav = Path(item["audio_file"])
        if not wav.exists():
            emit("D_zh_cer", {"label": item["label"], "error": "missing wav"})
            continue
        ref_text = item["text"]
        r = transcribe(wav, language="zh")
        if "error" in r:
            emit("D_zh_cer", {"label": item["label"], **r})
            continue
        c = cer(ref_text, r["text"])
        emit("D_zh_cer", {
            "label": item["label"], "audio": str(wav), "ref_text": ref_text, **r, **c,
        })

    # ---- E 英文 WER：aiden 合成的英文 ----
    en_item = next((x for x in tts["results"].get("E_english", []) if x.get("label") == "英文50字"), None)
    if en_item and Path(en_item["audio_file"]).exists():
        r = transcribe(Path(en_item["audio_file"]), language="en")
        if "error" in r:
            emit("E_en_wer", {"label": "aiden_50", **r})
        else:
            w = wer_en(en_item["text"], r["text"])
            emit("E_en_wer", {"label": "aiden_50", "audio": en_item["audio_file"],
                              "ref_text": en_item["text"], **r, **w})

    # ---- F 自动检测：不指定 language ----
    # 用 A1-50字作为样本
    sample_50 = next((x for x in tts["results"]["A_length_scaling"] if x["label"] == "50字"), None)
    if sample_50 and Path(sample_50["audio_file"]).exists():
        r = transcribe(Path(sample_50["audio_file"]), language=None)
        if "error" in r:
            emit("F_auto_detect", {"label": "50字_auto", **r})
        else:
            # 自动检测是否命中（zh 视为命中）
            hit = r["language"] == "zh"
            emit("F_auto_detect", {
                "label": "50字_auto", "audio": sample_50["audio_file"],
                "expected_language": "zh", **r,
                "hit": hit,
            })

    # ---- G 长音频漂移：1500 字长文 ----
    long_item = next((x for x in tts["results"].get("C_long_text", []) if x.get("label") == "1500字"), None)
    if long_item and Path(long_item["audio_file"]).exists():
        r = transcribe(Path(long_item["audio_file"]), language="zh", beam_size=5)
        if "error" in r:
            emit("G_long_audio", {"label": "1500字", **r})
        else:
            # 分段：前 1/3、中 1/3、尾 1/3 各自 CER
            n = len(r["segments"])
            third = max(1, n // 3)
            chunks = {
                "head": r["segments"][:third],
                "mid": r["segments"][third:2*third],
                "tail": r["segments"][2*third:],
            }
            drift = {}
            # 按时间窗口粗算对应原文区间（用字位置近似）
            ref_text = long_item["text"]
            ref_n = len(ref_text)
            total_dur = r["duration"]
            for k, segs in chunks.items():
                if not segs:
                    continue
                t_start = segs[0]["start"]
                t_end = segs[-1]["end"]
                # 原文窗口按时间比例切
                p_start = int(t_start / total_dur * ref_n)
                p_end = int(t_end / total_dur * ref_n)
                ref_chunk = ref_text[p_start:p_end]
                hyp_chunk = "".join(s["text"] for s in segs)
                drift[k] = cer(ref_chunk, hyp_chunk)
                drift[k]["time_range"] = [round(t_start, 1), round(t_end, 1)]
            emit("G_long_audio", {
                "label": "1500字", "audio": long_item["audio_file"], **r,
                "overall_cer": cer(long_item["text"], r["text"]),
                "chunk_cer": drift,
            })

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE ASR: sections={list(out['results'].keys())}", flush=True)


if __name__ == "__main__":
    main()