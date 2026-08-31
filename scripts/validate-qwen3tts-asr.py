#!/usr/bin/env python3
"""用本地 faster-whisper 对 Qwen3-TTS 四档成片做字符完整性复核。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from faster_whisper import WhisperModel


PUNCT = " \t\r\n，。！？、；：\"'()（）【】《》·.,!?;:\"'()[]<>-—…"


def make_text(length: int) -> str:
    sentences: list[str] = []
    index = 1
    while len("".join(sentences)) < length:
        sentences.append(
            f"这是第{index}段本地语音验收文本，用于检查长文本分段、音频拼接、响应完整性和服务恢复能力。"
        )
        index += 1
    text = "".join(sentences)[:length]
    return text[:-1] + "。"


def normalize(text: str) -> str:
    return "".join(char for char in text.lower() if char not in PUNCT and not char.isspace())


def levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        return levenshtein(right, left)
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def metrics(reference: str, hypothesis: str) -> dict:
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    edits = levenshtein(ref, hyp)
    tail_ref = ref[-60:]
    tail_hyp = hyp[-60:]
    tail_edits = levenshtein(tail_ref, tail_hyp)
    return {
        "reference_chars": len(ref),
        "hypothesis_chars": len(hyp),
        "length_ratio": round(len(hyp) / max(len(ref), 1), 4),
        "edits": edits,
        "cer": round(edits / max(len(ref), 1), 4),
        "tail_reference_chars": len(tail_ref),
        "tail_cer": round(tail_edits / max(len(tail_ref), 1), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model",
        default="/Users/jacky/voice-tools/models/models--Systran--faster-whisper-base/snapshots/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
    )
    args = parser.parse_args()

    model = WhisperModel(args.model, device="cpu", compute_type="int8", local_files_only=True)
    results = []
    for length in (15, 250, 500, 800):
        audio = args.input_dir / f"tts_{length}.mp3"
        started = time.monotonic()
        segments, info = model.transcribe(str(audio), language="zh", beam_size=5)
        segment_list = list(segments)
        hypothesis = "".join(segment.text for segment in segment_list)
        item = {
            "length": length,
            "audio": str(audio),
            "language": info.language,
            "audio_duration_seconds": round(info.duration, 3),
            "asr_elapsed_seconds": round(time.monotonic() - started, 3),
            "hypothesis": hypothesis,
            **metrics(make_text(length), hypothesis),
        }
        # 完整性与字词保真度分开：短样本 CER 对单个同音字极敏感；长文是否
        # 截断主要看转写长度比例和尾段是否存在。250 字以上另设 CER 0.25 门槛。
        item["complete"] = (
            0.85 <= item["length_ratio"] <= 1.15 and item["tail_cer"] <= 0.40
        )
        item["fidelity_pass"] = length < 250 or item["cer"] <= 0.25
        results.append(item)
        print(
            f"[asr] length={length} ratio={item['length_ratio']} "
            f"cer={item['cer']} tail_cer={item['tail_cer']} complete={item['complete']}",
            flush=True,
        )

    artifact = {
        "validator": "faster-whisper-base-cpu-int8",
        "results": results,
        "all_complete": all(item["complete"] for item in results),
        "long_text_fidelity_pass": all(item["fidelity_pass"] for item in results),
    }
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[asr] output={args.output} all_complete={artifact['all_complete']}", flush=True)
    if not artifact["all_complete"] or not artifact["long_text_fidelity_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
