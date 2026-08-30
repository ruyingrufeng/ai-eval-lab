#!/usr/bin/env python3
"""批量评测 runner：按阶段跑 T1-T12（配合 eval_agent.py）"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_agent import run_test, print_summary, TESTS

BASE = os.path.expanduser("~/llm-models/qwen35-eval")

def load_tasks():
    with open(os.path.join(TESTS, "tasks.json"), encoding="utf-8") as f:
        return json.load(f)

PHASES = {
    "gate": ["t3", "t4", "t5", "t7", "t8", "t11"],   # 智力闸门
    "long": ["t2", "t9", "t10"],                      # 长程能力
    "basic": ["t1", "t6", "t12"],                     # 基础/语义
    "all": None,
}

def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "gate"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    tasks = load_tasks()
    order = PHASES.get(phase)
    ids = order if order else list(tasks.keys())
    if only:
        ids = [only]
    summary = []
    for tid in ids:
        t = tasks[tid]
        wd = os.path.join(BASE, t["workdir"])
        os.makedirs(wd, exist_ok=True)
        kwargs = {}
        if t.get("middle_prompt"):
            kwargs = {"middle_prompt": t["middle_prompt"], "middle_at": t["middle_at"]}
        log = run_test(tid, t["prompt"], wd, t.get("max_steps", 30), **kwargs)
        print_summary(log)
        summary.append({"tid": tid, "name": t["name"], "e2e_s": log["e2e_s"],
                        "tool_calls": log["tool_calls"], "invalid": log["invalid"],
                        "dup": log["dup"], "final": log.get("final_answer", "")[:200]})
    with open(os.path.join(BASE, "results/summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\nsummary ->", f"{BASE}/results/summary.json")

if __name__ == "__main__":
    main()
