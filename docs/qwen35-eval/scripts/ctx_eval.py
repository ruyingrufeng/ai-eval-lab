#!/usr/bin/env python3
"""上下文压力测试执行器：16K/32K/64K/96K 档位"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_agent import llm_call, RESULTS, TESTS, snapshot_mem

CTX_DIR = os.path.join(TESTS, "ctx")
KEY = 128450.00

PROMPT_TMPL = """背景资料如下（公司季度运营档案）：

{text}

任务：根据这份资料，找出 2025 年 3 月 electronics 类别的总销售额。
注意：资料中只有标注为“可信记录·已审计”的条目是正式数据，标注“草稿/未审计”的不能用。
请直接给出你的答案（一行 FINAL_ANSWER: 数值）。"""

def main():
    levels = sys.argv[1:] or ["16k", "32k", "64k", "96k"]
    out = []
    for lv in levels:
        path = os.path.join(CTX_DIR, f"ctx_{lv}.txt")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        sys_msg = {"role": "system",
                   "content": "你是数据核对助手。阅读背景资料后直接回答一行：FINAL_ANSWER: 数值。"}
        usr = {"role": "user", "content": PROMPT_TMPL.format(text=text)}
        mem = []
        snapshot_mem(f"ctx_{lv}_start", mem)
        ans, usage, ttft, dts = llm_call([sys_msg, usr], max_tokens=256)
        snapshot_mem(f"ctx_{lv}_end", mem)
        correct = str(KEY) in ans.replace(",", "")
        r = {"level": lv, "prompt_tokens": usage["prompt_tokens"],
             "completion_tokens": usage["completion_tokens"],
             "ttft_ms": round(ttft * 1000, 1), "decode_tps": round(dts, 1),
             "answer": ans.strip()[:200], "correct": correct, "mem": mem}
        out.append(r)
        print(f"ctx_{lv}: prompt={usage['prompt_tokens']} tok, TTFT={r['ttft_ms']}ms, "
              f"decode={r['decode_tps']}t/s, correct={correct}")
        print(f"  answer: {ans.strip()[:120]}")
    with open(os.path.join(RESULTS, "ctx_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved ->", os.path.join(RESULTS, "ctx_results.json"))

if __name__ == "__main__":
    main()
