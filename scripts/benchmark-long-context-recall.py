#!/usr/bin/env python3
"""Measure deterministic needle recall from an approximately 16K-token prompt."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    with OPENER.open(request, timeout=timeout) as response:
        return json.load(response)


def filler(index: int) -> str:
    colors = ["灰", "绿", "紫", "橙", "白", "黑"]
    places = ["海港", "山城", "旧街", "南站", "河岸", "书院"]
    return (
        f"记录{index:04d}：{places[index % len(places)]}的值班员整理了"
        f"{colors[index % len(colors)]}色票据，并核对普通编号{1000 + index}。"
        "这只是背景资料，不是最终问题的答案；当天交通正常，物品均已归档。"
    )


def build_context(paragraphs: int) -> str:
    needles = {
        paragraphs // 8: "关键事实A：蓝色旅行笔记的暗号是『海岬-417』。",
        paragraphs * 3 // 8: "关键事实B：7:30火车的站台是『北站6号』。",
        paragraphs * 5 // 8: "关键事实C：红色雨伞的主人是『阿宁』。",
        paragraphs * 7 // 8: "关键事实D：最终确认短语是『琥珀-93』。",
    }
    parts = ["以下是很长的虚构旅行档案。请保留明确标成关键事实A至D的信息。"]
    for index in range(paragraphs):
        parts.append(filler(index))
        if index in needles:
            parts.append(needles[index])
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Base llama-server URL, e.g. http://127.0.0.1:8093")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-tokens", type=int, default=16000)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    paragraphs = 300
    while True:
        context = build_context(paragraphs)
        tokenized = post(f"{args.url}/tokenize", {"content": context, "add_special": False}, args.timeout)
        count = len(tokenized.get("tokens", []))
        if count >= args.target_tokens or paragraphs >= 2000:
            break
        paragraphs = max(paragraphs + 1, int(paragraphs * args.target_tokens / max(count, 1)) + 1)

    messages = [
        {"role": "system", "content": "只根据提供的档案回答，不要猜测，也不要解释推理过程。"},
        {"role": "user", "content": context},
        {
            "role": "user",
            "content": "请逐行回答A、B、C、D四项关键事实，只写对应答案。",
        },
    ]
    payload = {
        "model": args.model,
        "messages": messages,
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": 256,
        "stream": False,
        "seed": 16000,
    }
    started = time.monotonic()
    response = post(f"{args.url}/v1/chat/completions", payload, args.timeout)
    elapsed = round(time.monotonic() - started, 3)
    text = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    expected = ["海岬-417", "北站6号", "阿宁", "琥珀-93"]
    hits = {item: item in text.replace(" ", "") for item in expected}
    result = {
        "schema_version": 1,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": args.model,
        "target_tokens": args.target_tokens,
        "context_tokens_without_template": count,
        "paragraphs": paragraphs,
        "elapsed_seconds": elapsed,
        "usage": response.get("usage", {}),
        "answer": text,
        "expected": expected,
        "hits": hits,
        "score": f"{sum(hits.values())}/4",
        "pass": all(hits.values()),
        "error": response.get("error"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
