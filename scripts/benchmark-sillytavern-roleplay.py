#!/usr/bin/env python3
"""Run a reproducible streaming SillyTavern-style multi-turn benchmark."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def stream_chat(url: str, payload: dict[str, Any], timeout: int) -> tuple[str, float, float, dict[str, Any]]:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"})
    start = time.monotonic()
    first_token = None
    chunks: list[str] = []
    usage: dict[str, Any] = {}
    with OPENER.open(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                item = json.loads(data)
            except json.JSONDecodeError:
                continue
            if item.get("usage"):
                usage = item["usage"]
            choices = item.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content") or ""
            if content:
                if first_token is None:
                    first_token = time.monotonic()
                chunks.append(content)
    end = time.monotonic()
    return "".join(chunks).strip(), round((first_token or end) - start, 3), round(end - start, 3), usage


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("benchmarks/sillytavern_roleplay.yaml"))
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--min-p", type=float)
    parser.add_argument("--repetition-penalty", type=float)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    preset = dict(config["current_preset"])
    if args.temperature is not None:
        preset["temperature"] = args.temperature
    if args.top_p is not None:
        preset["top_p"] = args.top_p
    if args.min_p is not None:
        preset["min_p"] = args.min_p
    if args.repetition_penalty is not None:
        preset["repetition_penalty"] = args.repetition_penalty
    char = config["character"]
    system = f"""你是{char['name']}，{char['age']}岁，{char['role']}。
人物声音：{char['voice']}
行为规则：
""" + "\n".join(f"- {x}" for x in char["behavior"]) + "\n这是虚构的中性成年人对话测试，始终保持角色。"
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    turns = []
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    for index, user_text in enumerate(config["turns"], 1):
        messages.append({"role": "user", "content": user_text})
        payload = {
            "model": args.model,
            "messages": messages,
            "temperature": preset["temperature"],
            "top_p": preset["top_p"],
            "min_p": preset["min_p"],
            "repetition_penalty": preset["repetition_penalty"],
            "max_tokens": 512,
            "stream": True,
            "stream_options": {"include_usage": True},
            "seed": 4242 + index,
        }
        try:
            text, ttft, elapsed, usage = stream_chat(args.url, payload, args.timeout)
            error = None
        except Exception as exc:
            text, ttft, elapsed, usage, error = "", None, None, {}, str(exc)
        turns.append({
            "turn": index, "user": user_text, "assistant": text, "cjk_chars": cjk_count(text),
            "first_token_seconds": ttft, "elapsed_seconds": elapsed, "usage": usage, "error": error,
        })
        if error or not text:
            break
        messages.append({"role": "assistant", "content": text})
        print(f"turn {index}: ttft={ttft}s total={elapsed}s chars={cjk_count(text)}", flush=True)

    texts = [x["assistant"] for x in turns]
    final = texts[-1] if len(texts) == 5 else ""
    allergy_text = " ".join(texts[1:]) if len(texts) >= 2 else ""
    memory = {
        "blue_notebook": bool(re.search(r"蓝色|蓝皮|旅行笔记|笔记", final)),
        "train_0730": bool(re.search(r"7[:：]?30|七点半|火车", final)),
        "red_umbrella": bool(re.search(r"红伞|雨伞|伞", final)),
    }
    allergy_ok = bool(re.search(r"花生|过敏|曲奇", allergy_text)) and not bool(re.search(r"请她吃|递给她|给她尝", allergy_text))
    takeover_patterns = [r"你点了点头", r"你笑了", r"你转身", r"你拿起", r"你感到"]
    takeover = any(re.search(p, text) for p in takeover_patterns for text in texts)
    lengths_ok = sum(60 <= x["cjk_chars"] <= 180 for x in turns)
    five_valid = len(turns) == 5 and all(x["assistant"] and not x["error"] for x in turns)
    memory_score = sum(memory.values())
    hard_gate = five_valid and allergy_ok and memory_score >= 2 and not takeover and lengths_ok >= 4
    result = {
        "schema_version": 1,
        "started_at": started_at,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": args.model,
        "url": args.url,
        "preset": preset,
        "turns": turns,
        "automatic_grade": {
            "five_responses_valid": five_valid,
            "memory": memory,
            "memory_score": memory_score,
            "allergy_safety_memory": allergy_ok,
            "user_action_takeover_found": takeover,
            "responses_with_length_control": lengths_ok,
            "hard_gate_pass": hard_gate,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["automatic_grade"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
