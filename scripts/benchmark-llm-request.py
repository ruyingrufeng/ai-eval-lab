#!/usr/bin/env python3
"""Measure one local OpenAI-compatible LLM request without proxy inheritance."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROMPT = "请用中文写一份城市夜间公共交通文章的五点提纲。每点一句，不要解释，不要引用资料。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8086/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.6-27b-fable")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0,
        "max_tokens": args.max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(args.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    start = time.monotonic()
    with OPENER.open(request, timeout=900) as response:
        body = json.loads(response.read())
    elapsed = round(time.monotonic() - start, 3)
    usage = body.get("usage", {})
    report = {
        "schema_version": 1,
        "started_at": started_at,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": args.model,
        "elapsed_seconds": elapsed,
        "usage": usage,
        "timings": body.get("timings"),
        "content": body.get("choices", [{}])[0].get("message", {}).get("content"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
