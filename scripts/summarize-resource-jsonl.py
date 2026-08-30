#!/usr/bin/env python3
"""Summarize macOS resource samples and report deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit("no samples")

    def values(path):
        output = []
        for row in rows:
            value = row
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, (int, float)):
                output.append(value)
        return output

    def stats(path):
        numbers = values(path)
        if not numbers:
            return None
        return {"first": numbers[0], "last": numbers[-1], "min": min(numbers), "max": max(numbers), "delta": numbers[-1] - numbers[0]}

    summary = {
        "schema_version": 1,
        "source": str(args.input),
        "samples": len(rows),
        "started_at": rows[0]["recorded_at"],
        "ended_at": rows[-1]["recorded_at"],
        "duration_seconds": rows[-1]["epoch_seconds"] - rows[0]["epoch_seconds"],
        "memory_free_percent": stats(["memory_free_percent"]),
        "swap_used_mib": stats(["swap_used_mib"]),
        "free_pages": stats(["vm", "free_pages"]),
        "active_pages": stats(["vm", "active_pages"]),
        "wired_pages": stats(["vm", "wired_pages"]),
        "compressor_pages": stats(["vm", "compressor_pages"]),
        "pageouts": stats(["vm", "pageouts"]),
        "process_rss_kib": stats(["process", "rss_kib"]),
        "process_cpu_percent": stats(["process", "cpu_percent"]),
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
