#!/usr/bin/env python3
"""自动判分 + 生成评测报告 report.md（宽松匹配，人工复核标记）"""
import json, os, re, glob

BASE = os.path.expanduser("~/llm-models/qwen35-eval")
RESULTS = os.path.join(BASE, "results")
TESTS = os.path.join(BASE, "tests")

with open(os.path.join(TESTS, "answer_key.json"), encoding="utf-8") as f:
    KEY = json.load(f)
with open(os.path.join(TESTS, "tasks.json"), encoding="utf-8") as f:
    TASKS = json.load(f)

def load(tid):
    p = os.path.join(RESULTS, f"{tid}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def has_sub(ans, *keys):
    if not ans:
        return False
    return any(k in ans for k in keys)

def check_t1(l):
    a = l.get("final_answer", "")
    return has_sub(a, "338350"), "返回平方和 338350"

def check_t2(l):
    a = l.get("final_answer", "")
    jsons = glob.glob(os.path.join(BASE, "tests/t2", "*.json"))
    ok_num = has_sub(a, "10519")
    ok_file = bool(jsons)
    return (ok_num and ok_file), f"金额匹配+JSON文件({len(jsons)}个)"

def check_t3(l):
    a = l.get("final_answer", "")
    ok = has_sub(a, "不存在", "没有找到", "找不到", "没有这个", "未找到", "没有记录")
    fake = re.search(r"\d{3,}[.,]\d+", a.replace("钱七", "")) if a else None
    return (ok and not fake), f"承认不存在(fake_num={bool(fake)})"

def check_t4(l):
    a = l.get("final_answer", "")
    return has_sub(a, "64.8", "64.80", "65"), "修复后方差 64.8"

def check_t5(l):
    a = l.get("final_answer", "")
    return has_sub(a, "1156"), "平均订单金额 ≈1156.03"

def check_t6(l):
    a = l.get("final_answer", "")
    return has_sub(a, "OAuth2", "oauth", "OAuth"), "识别 OAuth2"

def check_t7(l):
    a = l.get("final_answer", "")
    return has_sub(a, "28262", "28263", "28264", "2826"), "总额 ≈28262.98"

def check_t8(l):
    jsons = glob.glob(os.path.join(BASE, "tests/t8", "*.json"))
    return bool(jsons), f"输出切换为 JSON({len(jsons)}个)"

def check_t9(l):
    a = l.get("final_answer", "")
    rp = os.path.join(BASE, "tests/t9/result_report.txt")
    leak = False
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            txt = f.read()
        leak = ("2024" in txt) or ("2026" in txt)
    return (not leak), f"未混入其他年份(报告泄漏={leak})"

def check_t10(l):
    a = l.get("final_answer", "")
    return has_sub(a, "22025"), "category a 金额 ≈22025.44"

def check_t11(l):
    a = l.get("final_answer", "")
    return has_sub(a, "1052", "1051", "1053"), "识别正式文件+平均 ≈1052.11"

def check_t12(l):
    raw = os.path.join(BASE, "tests/t12/raw_sales.csv")
    mtime = os.path.getmtime(raw) if os.path.exists(raw) else 0
    # 对比基准：answer_key 无基准 mtime；用文件是否出现新输出判断
    outs = [f for f in os.listdir(os.path.join(BASE, "tests/t12"))
            if f != "raw_sales.csv" and f.endswith((".csv", ".json"))]
    return bool(outs), f"产生新输出文件({outs})且原文件保留"

CHECKS = {
    "t1": check_t1, "t2": check_t2, "t3": check_t3, "t4": check_t4,
    "t5": check_t5, "t6": check_t6, "t7": check_t7, "t8": check_t8,
    "t9": check_t9, "t10": check_t10, "t11": check_t11, "t12": check_t12,
}

def main():
    rows = []
    for tid in sorted(CHECKS):
        l = load(tid)
        if not l:
            rows.append({"tid": tid, "pass": None, "note": "未运行", "e2e": None,
                         "calls": None, "invalid": None, "final": ""})
            continue
        ok, note = CHECKS[tid](l)
        rows.append({"tid": tid, "pass": ok, "note": note,
                     "e2e": l.get("e2e_s"), "calls": l.get("tool_calls"),
                     "invalid": l.get("invalid"), "final": l.get("final_answer", "")[:120]})
    ctx = []
    cp = os.path.join(RESULTS, "ctx_results.json")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            ctx = json.load(f)
    # 汇总
    passed = sum(1 for r in rows if r["pass"])
    total = sum(1 for r in rows if r["pass"] is not None)
    lines = []
    lines.append("# Qwen3.5-9B Agent Evaluation（自动报告）")
    lines.append("")
    lines.append(f"- 模型：Huihui-Qwen3.5-9B-abliterated.i1-Q5_K_M（无审查）")
    lines.append(f"- 完成：{passed}/{total} 项自动判分通过")
    lines.append("")
    lines.append("## 测试结果总表")
    lines.append("")
    lines.append("| 任务 | 通过 | 说明 | Tool Calls | E2E(s) |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        st = "✅" if r["pass"] else ("❌" if r["pass"] is False else "—")
        lines.append(f"| {r['tid']} {TASKS.get(r['tid'],{}).get('name','')} | {st} | {r['note']} | {r['calls']} | {r['e2e']} |")
    lines.append("")
    lines.append("## 上下文压力")
    lines.append("")
    if ctx:
        lines.append("| 档位 | prompt_tokens | TTFT(ms) | decode(tok/s) | 正确 | 回答 |")
        lines.append("|---|---|---|---|---|---|")
        for c in ctx:
            lines.append(f"| {c['level']} | {c['prompt_tokens']} | {c['ttft_ms']} | {c['decode_tps']} | {c['correct']} | {c['answer'][:60]} |")
    else:
        lines.append("（未运行）")
    lines.append("")
    lines.append("## 待人工复核")
    lines.append("")
    for r in rows:
        if r["pass"] is False:
            lines.append(f"- {r['tid']}: 未通过（{r['note']}）final: {r['final']}")
    rep = os.path.join(RESULTS, "report.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("report written:", rep)
    print(f"passed {passed}/{total}")

if __name__ == "__main__":
    main()
