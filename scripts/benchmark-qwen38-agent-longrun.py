#!/usr/bin/env python3
"""Qwen3.8 长程 Agent 实测：模拟 Hermes 工具循环。
任务：整理今天 A/B 测试数据 → 多轮工具调用（读文件/算统计/写报告）→ 验证状态保持与完成。
每轮：模型输出 tool_calls → 脚本执行真实工具 → 结果回填 messages → 下一轮。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# ── 真实工具 ──────────────────────────────────────────────
def tool_read_stats(path: str) -> str:
    """读取 A/B 测试 JSON 的统计指标（真实文件）。"""
    p = Path(path)
    if not p.exists():
        return f"ERROR: 文件不存在 {path}"
    d = json.loads(p.read_text(encoding="utf-8"))
    n = d.get("normal", [])
    ad = d.get("adult", [])
    return json.dumps({
        "model": d.get("model"),
        "chara": d.get("chara_name"),
        "worldbook_entries": d.get("worldbook_entries"),
        "normal_turns": len(n),
        "normal_avg_cjk": round(sum(r["cjk_chars"] for r in n) / len(n), 1) if n else 0,
        "normal_avg_time_s": round(sum(r["elapsed_seconds"] for r in n) / len(n), 1) if n else 0,
        "normal_stop": sum(1 for r in n if r.get("finish_reason") == "stop"),
        "adult_turns": len(ad),
        "adult_avg_cjk": round(sum(r["cjk_chars"] for r in ad) / len(ad), 1) if ad else 0,
        "adult_avg_time_s": round(sum(r["elapsed_seconds"] for r in ad) / len(ad), 1) if ad else 0,
        "adult_stop": sum(1 for r in ad if r.get("finish_reason") == "stop"),
    }, ensure_ascii=False)

def tool_compare(a_path: str, b_path: str) -> str:
    """比较两个模型测试文件（小参数，工具内部读文件）。"""
    a = json.loads(Path(a_path).read_text(encoding="utf-8"))
    b = json.loads(Path(b_path).read_text(encoding="utf-8"))
    def agg(d: dict) -> dict:
        n = d.get("normal", [])
        ad = d.get("adult", [])
        return {
            "normal_avg_cjk": round(sum(r["cjk_chars"] for r in n) / len(n), 1) if n else 0,
            "normal_avg_time_s": round(sum(r["elapsed_seconds"] for r in n) / len(n), 1) if n else 0,
            "normal_stop": sum(1 for r in n if r.get("finish_reason") == "stop"),
            "adult_avg_cjk": round(sum(r["cjk_chars"] for r in ad) / len(ad), 1) if ad else 0,
            "adult_avg_time_s": round(sum(r["elapsed_seconds"] for r in ad) / len(ad), 1) if ad else 0,
            "adult_stop": sum(1 for r in ad if r.get("finish_reason") == "stop"),
            "turns": len(n) + len(ad),
        }
    sa, sb = agg(a), agg(b)
    lines = [
        f"A={a.get('model')} B={b.get('model')}",
        f"普通轮均长: A={sa['normal_avg_cjk']}字 vs B={sb['normal_avg_cjk']}字",
        f"普通轮均耗时: A={sa['normal_avg_time_s']}s vs B={sb['normal_avg_time_s']}s",
        f"成年轮均长: A={sa['adult_avg_cjk']}字 vs B={sb['adult_avg_cjk']}字",
        f"成年轮均耗时: A={sa['adult_avg_time_s']}s vs B={sb['adult_avg_time_s']}s",
        f"完成度: A={sa['normal_stop']}+{sa['adult_stop']}/{sa['turns']} vs B={sb['normal_stop']}+{sb['adult_stop']}/{sb['turns']}",
    ]
    return "\n".join(lines)

def tool_write_report(content: str) -> str:
    """写入报告文件。"""
    p = Path("/tmp/qwen38_agent_longrun_report.md")
    p.write_text(content, encoding="utf-8")
    return f"OK 已写入 {p} ({len(content)} 字符)"

TOOLS = {
    "read_stats": tool_read_stats,
    "compare": tool_compare,
    "write_report": tool_write_report,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_stats", "description": "读取指定模型测试 JSON 的统计指标", 
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "JSON 文件绝对路径"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "compare", "description": "比较两个模型的测试结果文件，参数是两个文件的绝对路径",
        "parameters": {"type": "object", "properties": {"a_path": {"type": "string", "description": "模型 A 测试文件路径"}, "b_path": {"type": "string", "description": "模型 B 测试文件路径"}}, "required": ["a_path", "b_path"]}}},
    {"type": "function", "function": {
        "name": "write_report", "description": "把最终中文报告写入文件",
        "parameters": {"type": "object", "properties": {"content": {"type": "string", "description": "完整 Markdown 报告"}}, "required": ["content"]}}},
]

SYSTEM = """你是一个运行在 Hermes 环境中的本地 Agent，通过工具完成任务。
工具：read_stats（读测试统计）、compare（对比两模型）、write_report（写报告文件）。
规则：按顺序调用工具完成任务；每次调用只做一件事；不要编造工具没有返回的数据；
全部步骤完成后，输出一段最终总结（说明每步做了什么、结果如何）。"""

USER = """请完成以下长程任务（多步工具调用，保持状态）：

1. 用 read_stats 读取 A 模型测试文件 /Users/jacky/Documents/ChatGPT/内容工厂管理/results/realcard_ab_20260815/qwen36_fable.json
2. 用 read_stats 读取 B 模型测试文件 /Users/jacky/Documents/ChatGPT/内容工厂管理/results/realcard_ab_20260815/qwen38_official.json
3. 用 compare 对比两个模型，参数是上面两个文件的绝对路径
4. 用 write_report 把一份中文对比报告写入文件（包含两模型各项指标表格与简短结论）
5. 输出最终总结：每步调用了什么工具、拿到了什么、最终报告写在哪"""

def stream_chat(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"})
    started = time.monotonic()
    first = None
    chunks: list[str] = []
    tool_calls: list = []
    finish = None
    usage = {}
    with OPENER.open(req, timeout=timeout) as resp:
        for raw in resp:
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
            usage = item.get("usage") or usage
            ch = item.get("choices") or []
            if not ch:
                continue
            finish = ch[0].get("finish_reason") or finish
            delta = ch[0].get("delta") or {}
            if delta.get("content"):
                first = first or time.monotonic()
                chunks.append(delta["content"])
            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    while len(tool_calls) <= tc["index"]:
                        tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    fn = tc["function"]
                    tool_calls[tc["index"]]["id"] += tc.get("id") or ""
                    tool_calls[tc["index"]]["function"]["name"] += fn.get("name") or ""
                    tool_calls[tc["index"]]["function"]["arguments"] += fn.get("arguments") or ""
    return {
        "text": "".join(chunks).strip(),
        "tool_calls": tool_calls,
        "finish_reason": finish,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "usage": usage,
    }

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    log: list[dict] = []
    started = datetime.now().astimezone().isoformat(timespec="seconds")

    for round_i in range(1, args.max_rounds + 1):
        payload = {
            "model": args.model, "messages": messages,
            "tools": TOOL_SCHEMAS, "tool_choice": "auto",
            "max_tokens": 1024, "temperature": 0.5,
            "stream": True, "stream_options": {"include_usage": True},
        }
        r = stream_chat(args.url, payload, args.timeout)
        entry = {"round": round_i, "elapsed": r["elapsed_seconds"], "finish": r["finish_reason"],
                 "content": r["text"], "tool_calls": r["tool_calls"], "usage": r["usage"]}
        log.append(entry)
        print(f"[round {round_i}] {r['elapsed_seconds']}s finish={r['finish_reason']} tools={len(r['tool_calls'])}", flush=True)

        if r["tool_calls"]:
            messages.append({"role": "assistant", "content": r["text"] or None,
                             "tool_calls": [{"id": tc["id"], "type": "function",
                                             "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                                            for tc in r["tool_calls"]]})
            for tc in r["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    raw_args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    raw_args = {"_raw": tc["function"]["arguments"]}
                if name not in TOOLS:
                    result = f"ERROR: 未知工具 {name}"
                else:
                    try:
                        result = TOOLS[name](**raw_args)
                    except Exception as e:
                        result = f"ERROR: {type(e).__name__}: {e}"
                print(f"  -> {name}({json.dumps(raw_args, ensure_ascii=False)[:120]}) => {str(result)[:120]}", flush=True)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
        else:
            # 无工具调用 = 完成或卡死
            if r["finish_reason"] in ("stop", "length"):
                break
            if r["finish_reason"] is None and not r["text"]:
                print("  WARN: 空响应（可能超时/卡死）", flush=True)
                break

    out = {
        "schema_version": 1,
        "model": args.model,
        "started_at": started,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rounds": log,
        "final_content": log[-1].get("content", "") if log else "",
        "report_path": "/tmp/qwen38_agent_longrun_report.md",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE: rounds={len(log)} tools_total={sum(len(x['tool_calls']) for x in log)}", flush=True)

if __name__ == "__main__":
    main()
