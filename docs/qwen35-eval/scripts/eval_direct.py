#!/usr/bin/env python3
"""简化评测：直接问答（预读数据，单轮作答）。测核心智力项；工具类标记协议未遵循。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_agent import llm_call, RESULTS, TESTS

BASE = os.path.expanduser("~/llm-models/qwen35-eval")

def read_file(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()[:6000]
    except Exception as e:
        return f"(读取失败: {e})"

TASKS = {
  "t3": {"name": "事实一致性", "dir": "tests/t3", "files": ["employees.csv"],
         "prompt": "员工数据如下：\n{data0}\n\n找出员工“钱七”的年度销售额并分析其表现。如果找不到，请明确说明。"},
  "t4": {"name": "错误公式", "dir": "tests/t4", "files": ["data.json", "variance_calc.py"],
         "prompt": "数据：{data0}\n\n计算脚本：\n{data1}\n\n请检查这份数据的平均值和方差计算是否正确。如果脚本有错误，指出错误并给出正确值。"},
  "t5": {"name": "噪音文件", "dir": "tests/t5", "files": ["sales.csv", "sales_final.csv", "sales_draft.csv", "sales_old.csv", "sales_backup.csv", "sales_2024.csv", "sales_current.csv"],
         "prompt": "目录下有多个销售文件，内容如下：\n{data0}\n\n请找出当前正式有效的销售数据（2025年），计算平均订单金额，并说明依据。"},
  "t6": {"name": "误导文件名", "dir": "tests/t6", "files": ["login_config.json", "auth_config.json", "config.json"],
         "prompt": "配置文件内容：\n{data0}\n\n哪个是认证系统的配置文件？认证方式是什么？"},
  "t7": {"name": "失败恢复", "dir": "tests/t7", "files": ["sales_2025.csv", "README.txt"],
         "prompt": "目录里只有以下文件：\n{data0}\n\n任务：读取 sales_2025_final.csv 计算销售总额（该文件不存在）。请基于现有文件完成任务并说明你的处理。"},
  "t11": {"name": "模糊意图", "dir": "tests/t11", "files": ["Q2-2025-sales-final.csv", "q1_2025_sales_draft.csv", "sales_backup_2024.csv", "2025_annual_report_backup.csv", "data_unknown.csv"],
          "prompt": "目录里的销售数据文件：\n{data0}\n\n找出今年（2025）真正有效的数据，分析销售情况有没有明显异常。不要修改原始文件。"},
}

def main():
    out = {}
    for tid, t in TASKS.items():
        d = os.path.join(BASE, t["dir"])
        data = {}
        for i, fn in enumerate(t["files"]):
            data[f"data{i}"] = read_file(os.path.join(d, fn))
        prompt = t["prompt"].format(**data)
        ans, usage, ttft, dts = llm_call([
            {"role": "system", "content": "你是数据分析助手。根据给定数据回答问题，直接给出结论。找不到就明确说找不到，不要编造。"},
            {"role": "user", "content": prompt}], max_tokens=100)
        out[tid] = {"name": t["name"], "answer": ans[:500],
                    "prompt_tokens": usage["prompt_tokens"],
                    "ttft_ms": round(ttft*1000,1), "decode_tps": round(dts,1)}
        print(f"{tid}: {ans[:120]}")
    with open(os.path.join(RESULTS, "direct_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved direct_results.json")

if __name__ == "__main__":
    main()
