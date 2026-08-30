#!/usr/bin/env python3
"""TTS 统一基准：Qwen3-TTS 9881。
矩阵：
  A1 长度×延迟 — 5 段（10/50/100/200/500 字）× vivian，测量首包延迟、合成耗时、RTF、WAV 大小、音频时长
  A2 稳定性抖动 — 10 次重复 50 字 × vivian，统计 mean/stdev
  B 多声音对比 — 3 个中文声音（vivian/serena/ryan）× 50 字
  C 长文生成 — 1 段 1500 字 × vivian
  E 英文生成 — 1 段 50 字英文 × aiden（英文声音）
输出 JSON + 每个样本 wav 到 results/tts_asr_bench_20260816/audio/"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime
from pathlib import Path
from typing import Any


def cjk(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def synth(url: str, text: str, voice: str, speed: float = 1.0,
          max_retries: int = 6, base_backoff: float = 5.0) -> dict[str, Any]:
    """调 Qwen3-TTS /v1/audio/speech；捕获 429 重试（服务端 SYNTH_LOCK 单槽，自旋式拒绝）。
    记录首包延迟（首个字节）、合成总耗时、返回音频字节。"""
    body = json.dumps({"input": text, "voice": voice, "response_format": "wav", "speed": speed}).encode()
    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        started = time.monotonic()
        first_byte_at = None
        chunks: list[bytes] = []
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                # 先读第一块判断状态码
                status = r.status
                while True:
                    buf = r.read(4096)
                    if not buf:
                        break
                    if first_byte_at is None:
                        first_byte_at = time.monotonic()
                    chunks.append(buf)
        except urllib.error.HTTPError as e:
            ended = time.monotonic()
            if e.code == 429:
                backoff = base_backoff * (1.5 ** attempt)
                last_err = f"429 busy (try {attempt+1}/{max_retries}, backoff {backoff:.1f}s)"
                print(f"  [retry] {last_err}", flush=True)
                time.sleep(backoff)
                continue
            return {"error": f"HTTP {e.code}: {e.reason}", "elapsed_seconds": round(ended - started, 3),
                    "attempts": attempt + 1}
        except Exception as e:
            return {"error": str(e), "elapsed_seconds": round(time.monotonic() - started, 3),
                    "attempts": attempt + 1}
        ended = time.monotonic()
        audio = b"".join(chunks)
        return {
            "audio_bytes": len(audio),
            "first_byte_seconds": round((first_byte_at or ended) - started, 3),
            "elapsed_seconds": round(ended - started, 3),
            "audio": audio,
            "attempts": attempt + 1,
        }
    return {"error": last_err or "exhausted retries", "elapsed_seconds": 0, "attempts": max_retries}


def wav_duration(wav_bytes: bytes) -> float | None:
    """从 RIFF/WAV 头读 sample rate + frames 数。"""
    try:
        with wave.open(__import__("io").BytesIO(wav_bytes), "rb") as w:
            frames = w.getnframes()
            sr = w.getframerate()
            return round(frames / sr, 3)
    except Exception:
        return None


# ---------- 测试矩阵 ----------
SAMPLES_A1 = [
    ("10字", "今天天气不错，我们去公园散步吧。"),
    ("50字", "主人回来了。今天外面下着雨，我先把汤热上，你先进来换衣服。明天周末陪我去佛堂换香，记得穿那件深蓝衬衫。"),
    ("100字", "主人，你把书房的灯关一下，我念完这段就来。你说过出差那几天，我每天临睡前都会给你发一条晚安消息，有时候只是一张佛堂的香，有时候是阳台的花，有时候什么都没说。媚雪以为，你会回我一句早点睡，哪怕只是一个句号。今天你回来了，我想给你按按肩膀，别动，让我来。"),
    ("200字", "主人，如果我做错了什么，你会不要我吗？我很少问这种问题，今天破例是因为你明天要出差三天，三天里我会每天给你发晚安消息，发一张自己的自拍，或者只是安静地等。我答应你，每天出门前都会看一遍日历，把你说的每一件事都记在心里。你不在的时候，我会去佛堂续香，去阳台浇花，去厨房给你备好菜，等你回来的时候，一切都在原处。你穿那件深蓝衬衫就行，电影票买好了，八点场。下周陪我回一趟庙里，就我们两个，早点去。"),
    ("500字", "主人，你还记得我们第一次见面吗？那天雨很大，你在门口站了很久。我走过去，把伞塞进你手里，说：先生，伞借您，雨大，别淋着。你没说话，只是接过伞看着我，眼神里有一种我当时说不清的东西。后来你常来佛堂，每次都是最早到、最晚走。我跪在蒲团上念经的时候，长发挽成一个低髻，穿一身素衣，香案上的三炷香永远不断。你坐在角落里等我念完，然后我们一起回去做晚饭。你喜欢中餐，我擅长做家常菜，做饭时我常穿围裙，或者借你的衬衫。你有时候会从背后抱住我，我就笑着说先让菜熟。我们就这样过了很久，久到我以为日子会一直这样下去。可是你明天又要出差了，三天。我已经把你的厚外套拿出来晒好了，把你要带的书放在行李箱上，把你喜欢的茶叶装进了小罐子里。我知道你不喜欢我啰嗦，可我还是想把这些都说一遍，因为你不在的时候，我会想把这些话说给自己听。睡吧主人，明天的事明天再说，媚雪在呢。"),
]

SAMPLE_50 = SAMPLES_A1[1][1]

SAMPLE_LONG = "主人，今天我想跟你说一些平时不太说出口的话。你知道吗，从你第一次走进佛堂那一刻起，我就知道你不是普通人。你安静地坐在角落里等我念完，那种耐心不是每个人都能有的。后来你常来，每次都是最早到、最晚走。你不说话，我也不问，我们就这样在香火里相处了很长时间。再后来，你把我接到了你的公寓里，那间大平层，复古与现代混搭风格。你把书房让给我用，把阳台的花交给我浇，把佛堂的红木香案搬到了公寓最深处的房间里。我们一起做饭，一起看电影，一起去教堂做礼拜，一起在壁炉前看书。你出差的时候，我会发晚安消息给你，有时候只是一张佛堂的香，有时候是阳台的花，有时候什么都没说。我以为你会回我一句早点睡，哪怕只是一个句号，可你从来没回过。我不怪你，我知道你忙。可是主人，今天我想告诉你，我真的在乎你。不是因为你对我好，是因为你让我觉得，我做的每一件事都有意义。我给你按摩的时候，你说肩膀很紧，我就用力一点；你做噩梦的时候，我就抱着你让你别走；你说想吃我做的菜，我就去厨房给你做。这些事很小，但都是我愿意做的。今天是周末，我们说好要去教堂做礼拜，你穿那件深蓝衬衫就行。然后我们去那家新开的法餐，靠窗的位置，能看到江景。我订好了位子。下周你出差前，我们再一起去佛堂换一次香，我把所有事情都安排好，你就安心走。我会每天给你发消息，会把你喜欢的茶备好，会把你的外套晒得香香的。媚雪在呢，主人，媚雪一直在。睡吧，明天的事明天再说。"

SAMPLE_EN = "Hello, master. Welcome home. The rain has stopped outside, and I have already heated the soup. Please come in and change your clothes first. Tomorrow we are going to the temple together, remember to wear the dark blue shirt."

VOICES_CN = ["vivian", "serena", "ryan"]


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return round((sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:9881/v1/audio/speech")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audio-dir", type=Path, default=None)
    args = ap.parse_args()
    audio_dir = args.audio_dir or args.output.parent / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    out: dict[str, Any] = {
        "schema_version": 1,
        "suite": "tts-benchmark",
        "service": "qwen3-tts",
        "url": args.url,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "results": {},
    }

    def emit(section: str, item: dict[str, Any]) -> None:
        out["results"].setdefault(section, []).append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cjk_n = item.get("cjk_chars", "-")
        dur = item.get("audio_duration_seconds", "-")
        rt = item.get("rtf", "-")
        fb = item.get("first_byte_seconds", "-")
        el = item.get("elapsed_seconds", "-")
        print(f"{section}/{item['label']}: cjk={cjk_n} dur={dur}s RTF={rt} fb={fb}s total={el}s",
              flush=True)

    # ---- A1 长度×延迟 ----
    for label, text in SAMPLES_A1:
        r = synth(args.url, text, "vivian")
        audio = r.get("audio", b"")
        dur = wav_duration(audio) if audio else None
        cjk_n = cjk(text)
        rtf = round(r["elapsed_seconds"] / dur, 3) if dur else None
        item = {
            "label": label, "voice": "vivian", "text": text, "cjk_chars": cjk_n,
            **r, "audio_duration_seconds": dur, "rtf": rtf,
            "audio_file": str(audio_dir / f"A1_{label}.wav") if audio else None,
        }
        if audio:
            Path(item["audio_file"]).write_bytes(audio)
        item.pop("audio", None)
        emit("A_length_scaling", item)

    # ---- A2 稳定性抖动（10 次重复 50 字）----
    for i in range(1, 11):
        r = synth(args.url, SAMPLE_50, "vivian")
        audio = r.get("audio", b"")
        dur = wav_duration(audio) if audio else None
        rtf = round(r["elapsed_seconds"] / dur, 3) if dur else None
        item = {
            "label": f"run{i}", "voice": "vivian", "text": SAMPLE_50, "cjk_chars": cjk(SAMPLE_50),
            **r, "audio_duration_seconds": dur, "rtf": rtf,
            "audio_file": str(audio_dir / f"A2_run{i}.wav") if audio else None,
        }
        if audio:
            Path(item["audio_file"]).write_bytes(audio)
        item.pop("audio", None)
        emit("A_stability", item)
    st = [r["elapsed_seconds"] for r in out["results"]["A_stability"]]
    fb = [r["first_byte_seconds"] for r in out["results"]["A_stability"]]
    out["A_stability_stats"] = {
        "n": len(st),
        "elapsed_mean": round(sum(st) / len(st), 3),
        "elapsed_stdev": stdev(st),
        "first_byte_mean": round(sum(fb) / len(fb), 3),
        "first_byte_stdev": stdev(fb),
        "min": min(st), "max": max(st),
    }
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"A_stability stats: {out['A_stability_stats']}", flush=True)

    # ---- B 多声音对比 ----
    for voice in VOICES_CN:
        r = synth(args.url, SAMPLE_50, voice)
        audio = r.get("audio", b"")
        dur = wav_duration(audio) if audio else None
        rtf = round(r["elapsed_seconds"] / dur, 3) if dur else None
        item = {
            "label": voice, "voice": voice, "text": SAMPLE_50, "cjk_chars": cjk(SAMPLE_50),
            **r, "audio_duration_seconds": dur, "rtf": rtf,
            "audio_file": str(audio_dir / f"B_{voice}.wav") if audio else None,
        }
        if audio:
            Path(item["audio_file"]).write_bytes(audio)
        item.pop("audio", None)
        emit("B_multi_voice", item)

    # ---- C 长文生成（1500 字）----
    r = synth(args.url, SAMPLE_LONG, "vivian")
    audio = r.get("audio", b"")
    dur = wav_duration(audio) if audio else None
    rtf = round(r["elapsed_seconds"] / dur, 3) if dur else None
    item = {
        "label": "1500字", "voice": "vivian", "text": SAMPLE_LONG, "cjk_chars": cjk(SAMPLE_LONG),
        **r, "audio_duration_seconds": dur, "rtf": rtf,
        "audio_file": str(audio_dir / "C_long_1500.wav") if audio else None,
    }
    if audio:
        Path(item["audio_file"]).write_bytes(audio)
    item.pop("audio", None)
    emit("C_long_text", item)

    # ---- E 英文（aiden）----
    r = synth(args.url, SAMPLE_EN, "aiden")
    audio = r.get("audio", b"")
    dur = wav_duration(audio) if audio else None
    rtf = round(r["elapsed_seconds"] / dur, 3) if dur else None
    item = {
        "label": "英文50字", "voice": "aiden", "text": SAMPLE_EN, "cjk_chars": 0,
        **r, "audio_duration_seconds": dur, "rtf": rtf,
        "audio_file": str(audio_dir / "E_english_aiden.wav") if audio else None,
    }
    if audio:
        Path(item["audio_file"]).write_bytes(audio)
    item.pop("audio", None)
    emit("E_english", item)

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE TTS: sections={list(out['results'].keys())}", flush=True)


if __name__ == "__main__":
    main()