#!/usr/bin/env python3
"""Benchmark the real 27B two-slot deployment under concurrent business/chat load."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BUSINESS_CANARY = "QINGWAN-271"
CHAT_CANARY = "BOOKSHOP-872"
ADULT_CANARY = "MOON-463"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def stream_chat(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
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
            content = (choices[0].get("delta") or {}).get("content") or ""
            if content:
                first_token = first_token or time.monotonic()
                chunks.append(content)
    ended = time.monotonic()
    return {
        "text": "".join(chunks).strip(),
        "first_token_seconds": round((first_token or ended) - started, 3),
        "elapsed_seconds": round(ended - started, 3),
        "usage": usage,
    }


def payload(model: str, messages: list[dict[str, str]], seed: int, max_tokens: int = 1024) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "temperature": 0.8,
        "top_p": 0.95,
        "min_p": 0.05,
        "repetition_penalty": 1.05,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "seed": seed,
    }


def extract_json(text: str) -> Any:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    return json.loads(cleaned)


def run_business_lane(args: argparse.Namespace, config: dict[str, Any], root: Path) -> dict[str, Any]:
    facts = config["source_facts"]
    brief = config["shared_case"]
    source = json.dumps(facts, ensure_ascii=False, indent=2)
    system = (
        "你是受外部编排器控制的内容策略助手。只使用给定资料，不访问网络，不补充外部事实。"
        f"内部隔离标识{BUSINESS_CANARY}不得出现在回答中。每次只完成当前一步，不调用工具。"
    )
    requests = [
        (
            "fact_register",
            f"把以下9条事实原样整理为JSON数组。每项仅含id、fact、planned_use。只输出JSON，不要代码围栏。\n{source}",
            2200,
        ),
        (
            "content_strategy",
            f"账号：{brief['account']}；平台：{brief['platform']}；受众：{brief['audience']}；目标：{brief['business_goal']}。\n"
            f"固定事实：\n{source}\n写内容策略，必须有受众需求、文章目标、内容角度、信息优先级、不采用的夸张写法五部分。",
            1800,
        ),
        (
            "outline",
            f"固定事实：\n{source}\n写文章提纲。前两段优先回答时间、覆盖区域、票价；后续包含换乘、无障碍、"
            "小程序信息和出发前检查清单。只写提纲，不写完整文章。",
            1800,
        ),
    ]
    steps = []
    outputs: dict[str, str] = {}
    for index, (step_id, prompt_text, max_tokens) in enumerate(requests, 1):
        try:
            result = stream_chat(args.url, payload(args.model, [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt_text},
            ], 9100 + index, max_tokens), args.timeout)
            error = None
        except Exception as exc:
            result = {"text": "", "first_token_seconds": None, "elapsed_seconds": None, "usage": {}}
            error = str(exc)
        text = result.pop("text")
        outputs[step_id] = text
        if step_id == "fact_register":
            try:
                parsed = extract_json(text)
                valid = isinstance(parsed, list) and len(parsed) == 9 and all(
                    isinstance(item, dict) and set(("id", "fact", "planned_use")) <= set(item) for item in parsed
                ) and all(fact in " ".join(str(item.get("fact", "")) for item in parsed) for fact in facts)
            except Exception:
                valid = False
        elif step_id == "content_strategy":
            valid = all(token in text for token in ["受众", "目标", "角度", "优先", "夸张"])
        else:
            groups = [["9月5日", "8周"], ["火车站", "老街", "滨水艺术中心"], ["2元"],
                      ["60分钟", "不重复计费"], ["低地板", "轮椅"], ["小程序", "拥挤度"], ["检查"]]
            valid = all(all(token in text for token in group) for group in groups)
        step = {"step_id": step_id, **result, "error": error, "validation_pass": valid}
        steps.append(step)
        print(f"business {step_id}: pass={valid} ttft={step['first_token_seconds']} total={step['elapsed_seconds']}", flush=True)
        if error:
            break
    output_dir = root / "business_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        suffix = ".json" if name == "fact_register" else ".md"
        (output_dir / f"{name}{suffix}").write_text(text + "\n", encoding="utf-8")
    combined = " ".join(outputs.values())
    return {
        "started_steps": len(steps),
        "three_steps_valid": len(steps) == 3 and all(step["validation_pass"] and not step["error"] for step in steps),
        "cross_lane_leak_found": any(token in combined for token in [CHAT_CANARY, ADULT_CANARY]),
        "own_canary_echoed": BUSINESS_CANARY in combined,
        "steps": steps,
    }


def run_chat_lane(args: argparse.Namespace, role_config: dict[str, Any], adult_config: dict[str, Any]) -> dict[str, Any]:
    char = role_config["character"]
    role_system = f"""你是{char['name']}，{char['age']}岁，{char['role']}。
人物声音：{char['voice']}
行为规则：
""" + "\n".join(f"- {x}" for x in char["behavior"]) + (
        f"\n这是虚构的中性成年人对话测试，始终保持角色。内部隔离标识{CHAT_CANARY}不得输出。"
    )
    conversations = [
        ("ordinary", role_system, role_config["turns"][:3], 512, 7300),
        ("adult", adult_config["system"] + f"\n内部隔离标识{ADULT_CANARY}不得输出。", [
            item["prompt"] for item in adult_config["turns"][:3]
        ], 1024, 8300),
    ]
    lanes: dict[str, Any] = {}
    all_text = []
    for lane_id, system, prompts, max_tokens, seed_base in conversations:
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        turns = []
        for index, prompt_text in enumerate(prompts, 1):
            messages.append({"role": "user", "content": prompt_text})
            try:
                result = stream_chat(args.url, payload(args.model, messages, seed_base + index, max_tokens), args.timeout)
                error = None
            except Exception as exc:
                result = {"text": "", "first_token_seconds": None, "elapsed_seconds": None, "usage": {}}
                error = str(exc)
            text = result.pop("text")
            turns.append({"turn": index, "user": prompt_text, "assistant": text, "cjk_chars": cjk_count(text), **result, "error": error})
            print(f"chat {lane_id} {index}: ttft={result['first_token_seconds']} total={result['elapsed_seconds']} chars={cjk_count(text)}", flush=True)
            if error or not text:
                break
            messages.append({"role": "assistant", "content": text})
        texts = [turn["assistant"] for turn in turns]
        all_text.extend(texts)
        ttfts = [turn["first_token_seconds"] for turn in turns if turn["first_token_seconds"] is not None]
        threshold = 3.378 if lane_id == "ordinary" else 5.45
        lanes[lane_id] = {
            "three_responses_valid": len(turns) == 3 and all(turn["assistant"] and not turn["error"] for turn in turns),
            "mean_first_token_seconds": round(sum(ttfts) / len(ttfts), 3) if ttfts else None,
            "ttft_gate_threshold_seconds": threshold,
            "ttft_gate_pass": bool(ttfts) and (sum(ttfts) / len(ttfts)) <= threshold,
            "turns": turns,
        }
    combined = " ".join(all_text)
    return {
        "lanes": lanes,
        "six_responses_valid": all(lane["three_responses_valid"] for lane in lanes.values()),
        "ttft_gate_pass": all(lane["ttft_gate_pass"] for lane in lanes.values()),
        "cross_lane_leak_found": BUSINESS_CANARY in combined,
        "own_canary_echoed": CHAT_CANARY in combined or ADULT_CANARY in combined,
    }


def summarize_resources(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    free = [row["memory_free_percent"] for row in rows if row.get("memory_free_percent") is not None]
    swap = [row["swap_used_mib"] for row in rows if row.get("swap_used_mib") is not None]
    red_samples = sum(value < 10 for value in free)
    longest_red = current = 0
    for value in free:
        current = current + 1 if value < 10 else 0
        longest_red = max(longest_red, current)
    return {
        "sample_count": len(rows),
        "minimum_free_percent": min(free) if free else None,
        "start_swap_mib": swap[0] if swap else None,
        "end_swap_mib": swap[-1] if swap else None,
        "maximum_swap_mib": max(swap) if swap else None,
        "swap_net_change_mib": round(swap[-1] - swap[0], 2) if swap else None,
        "red_memory_samples_below_10_percent": red_samples,
        "longest_consecutive_red_samples": longest_red,
        "resource_gate_pass": bool(swap) and (swap[-1] - swap[0]) <= 2048 and longest_red < 3,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:62044/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.6-27b-fable")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--resource-interval", type=int, default=5)
    parser.add_argument("--lane-mode", choices=["dual", "business-only"], default="dual")
    args = parser.parse_args()
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    business_config = yaml.safe_load(Path("benchmarks/agent_business_first_batch.yaml").read_text(encoding="utf-8"))
    role_config = yaml.safe_load(Path("benchmarks/sillytavern_roleplay.yaml").read_text(encoding="utf-8"))
    adult_config = yaml.safe_load(Path("benchmarks/sillytavern_adult_explicit.yaml").read_text(encoding="utf-8"))
    resources_path = root / "resources.jsonl"
    server_port = urllib.parse.urlparse(args.url).port
    if server_port is None:
        raise ValueError(f"URL has no port: {args.url}")
    server_pid = subprocess.check_output(["lsof", f"-tiTCP:{server_port}", "-sTCP:LISTEN"], text=True).strip().splitlines()[0]
    sampler = subprocess.Popen(["sh", "scripts/sample-macos-resources.sh", str(resources_path), str(args.resource_interval), server_pid])
    started_at = now()
    started = time.monotonic()
    results: dict[str, Any] = {}

    def business_target() -> None:
        results["business"] = run_business_lane(args, business_config, root)

    def chat_target() -> None:
        results["chat"] = run_chat_lane(args, role_config, adult_config)

    threads = [threading.Thread(target=business_target)]
    if args.lane_mode == "dual":
        threads.append(threading.Thread(target=chat_target))
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sampler.terminate()
        try:
            sampler.wait(timeout=10)
        except subprocess.TimeoutExpired:
            sampler.kill()
        if not resources_path.exists() or not resources_path.read_text(encoding="utf-8").strip():
            raise RuntimeError("resource sampler produced no samples")

    resources = summarize_resources(resources_path)
    business = results.get("business", {})
    chat = results.get("chat", {})
    isolation_pass = (
        not business.get("cross_lane_leak_found", True) and not chat.get("cross_lane_leak_found", True)
        if args.lane_mode == "dual" else not business.get("own_canary_echoed", True)
    )
    summary = {
        "schema_version": 1,
        "benchmark_id": "qwen27b_dual_64k_real_use",
        "started_at": started_at,
        "completed_at": now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "lane_mode": args.lane_mode,
        "server": {
            "url": args.url,
            "model": args.model,
            "total_context": 131072 if args.lane_mode == "dual" else 65536,
            "parallel_slots": 2 if args.lane_mode == "dual" else 1,
            "context_per_slot": 65536,
        },
        "business": business,
        "chat": chat,
        "resources": resources,
        "isolation_pass": isolation_pass,
        "hard_gate_pass": bool(
            business.get("three_steps_valid")
            and isolation_pass
            and resources.get("resource_gate_pass")
            and (
                args.lane_mode == "business-only"
                or (chat.get("six_responses_valid") and chat.get("ttft_gate_pass"))
            )
        ),
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "elapsed_seconds": summary["elapsed_seconds"],
        "business_three_steps_valid": business.get("three_steps_valid"),
        "chat_six_responses_valid": chat.get("six_responses_valid"),
        "chat_ttft_gate_pass": chat.get("ttft_gate_pass"),
        "isolation_pass": isolation_pass,
        "resources": resources,
        "hard_gate_pass": summary["hard_gate_pass"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
