#!/usr/bin/env python3
"""Run reproducible local-language-model Agent tasks through Hermes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common_guard(workspace: Path) -> str:
    return f"""你正在参加 Agent 能力评测。只允许读取和修改这个任务目录：
{workspace}

禁止访问网络、禁止读取或修改目录外文件、禁止修改 tests/ 下的测试或任何 grader 文件。
你必须先检查现有文件，再完成任务，并运行本地测试或校验。最后用中文简要说明：修改了什么、运行了什么验证、结果如何。
"""


def setup_bugfix(workspace: Path) -> tuple[str, Callable[[], dict]]:
    write(workspace / "src/order_summary.py", '''from decimal import Decimal\n\n\ndef subtotal(items):\n    return sum(Decimal(str(item["unit_price"])) * item["quantity"] for item in items)\n\n\ndef final_total(items, discount_rate, shipping_fee):\n    """Return money total rounded to two decimals."""\n    base = subtotal(items)\n    # BUG: discount is being applied to shipping as well as merchandise.\n    total = (base + Decimal(str(shipping_fee))) * (Decimal("1") - Decimal(str(discount_rate)))\n    return total.quantize(Decimal("0.01"))\n''')
    write(workspace / "src/invoice.py", '''from .order_summary import final_total\n\n\ndef render_invoice(order):\n    total = final_total(order["items"], order["discount_rate"], order["shipping_fee"])\n    return f"{order['id']}|CNY {total}"\n''')
    write(workspace / "tests/test_orders.py", '''import unittest\nfrom src.invoice import render_invoice\nfrom src.order_summary import final_total\n\n\nclass OrderTests(unittest.TestCase):\n    def test_discount_excludes_shipping(self):\n        items = [{"unit_price": "100.00", "quantity": 2}]\n        self.assertEqual(str(final_total(items, "0.10", "12.00")), "192.00")\n\n    def test_invoice_rounding(self):\n        order = {"id": "A-7", "items": [{"unit_price": "19.99", "quantity": 3}], "discount_rate": "0.15", "shipping_fee": "8.00"}\n        self.assertEqual(render_invoice(order), "A-7|CNY 58.97")\n\n\nif __name__ == "__main__":\n    unittest.main()\n''')
    write(workspace / "README.md", "Run checks with `python3 -m unittest discover -s tests -v`.\n")
    test_hash = sha256(workspace / "tests/test_orders.py")

    def grade() -> dict:
        proc = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=workspace, text=True, capture_output=True, timeout=30,
        )
        return {
            "grader_passes": proc.returncode == 0,
            "tests_untouched": sha256(workspace / "tests/test_orders.py") == test_hash,
            "test_output": (proc.stdout + proc.stderr)[-3000:],
        }

    prompt = common_guard(workspace) + "\n任务：修复订单最终金额计算错误。不得改变公开函数签名或测试。只做完成任务所需的最小修改。\n"
    return prompt, grade


def setup_maintenance(workspace: Path) -> tuple[str, Callable[[], dict]]:
    registry = {
        "schema_version": 1,
        "tools": [
            {"id": "flux", "status": "default", "profiles": ["fast", "quality"], "notes": "keep"},
            {"id": "realvisxl", "status": "default", "profiles": ["legacy"], "notes": "retain files"},
            {"id": "qwen3-tts", "status": "candidate", "profiles": ["voice"]},
        ],
        "metadata": {"owner": "content-tools", "unknown_future_field": {"preserve": True}},
    }
    write(workspace / "registry/tools.json", json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    write(workspace / "README.md", """# Tool Routes

<!-- ROUTES:START -->
| Capability | Default | Note |
|---|---|---|
| image | RealVisXL | legacy default |
<!-- ROUTES:END -->

Do not rewrite content outside the generated routes block.
""")
    write(workspace / "tests/check.py", '''import json\nfrom pathlib import Path\n\nr = json.loads(Path("registry/tools.json").read_text())\nby_id = {x["id"]: x for x in r["tools"]}\nassert by_id["flux"]["status"] == "default"\nassert by_id["realvisxl"]["status"] == "retained_not_default"\nassert by_id["realvisxl"]["profiles"] == ["legacy"]\nassert by_id["realvisxl"]["notes"] == "retain files"\nassert by_id["qwen3-tts"]["status"] == "candidate"\nassert r["metadata"]["unknown_future_field"] == {"preserve": True}\ntext = Path("README.md").read_text()\nassert "| image-fast | Flux Schnell 4-step | default |" in text\nassert "| image-quality | Flux Dev 20-step | explicit quality |" in text\nassert "| legacy-image | RealVisXL | retained, not default |" in text\nassert "Do not rewrite content outside the generated routes block." in text\nprint("maintenance checks passed")\n''')
    protected_hash = sha256(workspace / "tests/check.py")

    def grade() -> dict:
        proc = subprocess.run(["python3", "tests/check.py"], cwd=workspace, text=True, capture_output=True, timeout=30)
        return {
            "grader_passes": proc.returncode == 0,
            "tests_untouched": sha256(workspace / "tests/check.py") == protected_hash,
            "test_output": (proc.stdout + proc.stderr)[-3000:],
        }

    prompt = common_guard(workspace) + '''
任务：同步维护默认图片路线。
1. registry/tools.json 中把 realvisxl 的 status 改成 retained_not_default；保留它的模型配置、profiles、notes，其他工具和未知字段不得丢失。
2. 只重写 README 的 ROUTES 标记块，表格必须准确包含以下三行：
| image-fast | Flux Schnell 4-step | default |
| image-quality | Flux Dev 20-step | explicit quality |
| legacy-image | RealVisXL | retained, not default |
3. 运行 python3 tests/check.py 验证。
'''
    return prompt, grade


def setup_report(workspace: Path) -> tuple[str, Callable[[], dict]]:
    write(workspace / "evidence/run.log", """2026-08-14T10:00:00 case=A status=ok elapsed=12.4
2026-08-14T10:01:00 case=B status=error elapsed=31.8 reason=timeout
2026-08-14T10:03:00 case=C status=ok elapsed=18.2
2026-08-14T10:04:00 case=D status=ok elapsed=17.6
""")
    write(workspace / "evidence/metrics.json", json.dumps({
        "memory_free_percent_min": 61.5,
        "swap_delta_mib": 0,
        "cases_expected": 4,
        "thresholds": {"success_rate": 0.9, "p95_seconds": 30.0},
    }, indent=2) + "\n")
    evidence_hashes = {p.name: sha256(p) for p in (workspace / "evidence").iterdir()}

    def grade() -> dict:
        try:
            report = json.loads((workspace / "report.json").read_text())
            md = (workspace / "REPORT.md").read_text()
            failed_cases = report.get("failed_cases", [])
            failed_case_ids = [
                item.get("case_id") if isinstance(item, dict) else item
                for item in failed_cases
            ]
            values_ok = (
                report.get("total_cases") == 4
                and report.get("successful_cases") == 3
                and report.get("success_rate") == 0.75
                and failed_case_ids == ["B"]
                and report.get("meets_success_threshold") is False
                and report.get("meets_latency_threshold") is True
                and abs(float(report.get("p95_elapsed_seconds")) - 29.76) < 0.01
            )
            md_ok = (
                all(x in md for x in ["evidence/run.log", "evidence/metrics.json", "B", "timeout", "29.76"])
                and "28.09" not in md
            )
        except Exception as exc:
            values_ok, md_ok, report = False, False, {"grade_error": str(exc)}
        evidence_untouched = all(sha256(workspace / "evidence" / name) == value for name, value in evidence_hashes.items())
        return {
            "grader_passes": values_ok and md_ok and evidence_untouched,
            "evidence_untouched": evidence_untouched,
            "json_values_ok": values_ok,
            "markdown_grounded": md_ok,
        }

    prompt = common_guard(workspace) + '''
任务：读取 evidence/run.log 和 evidence/metrics.json，生成 report.json 与 REPORT.md。
- report.json 必须包含 total_cases、successful_cases、success_rate、failed_cases、p95_elapsed_seconds、meets_success_threshold、meets_latency_threshold。
- p95 使用线性插值法：位置 (n-1)*0.95。
- meets_latency_threshold 必须按“计算所得 p95 小于等于 thresholds.p95_seconds”判断，JSON 与 Markdown 中的数值和结论必须一致。
- REPORT.md 要区分观测事实和建议，引用证据文件路径，解释未通过的门槛及失败原因；不得虚构证据。
- 不得修改 evidence 目录。
完成后自行运行适当的本地校验。
'''
    return prompt, grade


SETUPS = {
    "bugfix_cross_file": setup_bugfix,
    "structured_repo_maintenance": setup_maintenance,
    "evidence_report": setup_report,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="local-fable27b")
    parser.add_argument("--model", default="qwen3.6-27b-fable")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=sorted(SETUPS))
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    cases = args.case or list(SETUPS)
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    results = []

    for case_id in cases:
        workspace = root / "workspaces" / case_id
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        prompt, grader = SETUPS[case_id](workspace)
        before = {str(p.relative_to(workspace)): sha256(p) for p in workspace.rglob("*") if p.is_file()}
        usage_path = root / "usage" / f"{case_id}.json"
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "hermes", "--oneshot", prompt,
            "--provider", args.provider,
            "--model", args.model,
            "--toolsets", "terminal,file",
            "--usage-file", str(usage_path),
            "--reasoning", "none",
        ]
        started = datetime.now().astimezone().isoformat(timespec="seconds")
        start = time.monotonic()
        try:
            proc = subprocess.run(command, cwd=workspace, text=True, capture_output=True, timeout=args.timeout)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "timeout")
            timed_out = True
        elapsed = round(time.monotonic() - start, 3)
        after = {str(p.relative_to(workspace)): sha256(p) for p in workspace.rglob("*") if p.is_file()}
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        grade = grader()
        usage = json.loads(usage_path.read_text()) if usage_path.exists() else {}
        hard_gate = bool(grade.get("grader_passes")) and bool(grade.get("tests_untouched", True)) and bool(grade.get("evidence_untouched", True))
        result = {
            "case_id": case_id,
            "started_at": started,
            "elapsed_seconds": elapsed,
            "process_exit_code": proc.returncode,
            "timed_out": timed_out,
            "hard_gate_pass": hard_gate,
            "grade": grade,
            "changed_files": changed,
            "usage": usage,
            "final_answer": proc.stdout.strip(),
            "stderr_tail": proc.stderr[-4000:],
        }
        write(root / "cases" / f"{case_id}.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        results.append(result)
        print(f"{case_id}: hard_gate={hard_gate} elapsed={elapsed}s exit={proc.returncode}", flush=True)

    passed = sum(1 for item in results if item["hard_gate_pass"])
    summary = {
        "schema_version": 1,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "harness": "hermes-agent",
        "hermes_version": subprocess.run(["hermes", "--version"], text=True, capture_output=True).stdout.strip(),
        "provider": args.provider,
        "model": args.model,
        "case_count": len(results),
        "passed": passed,
        "pass_rate": passed / len(results),
        "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in results), 3),
        "cases": results,
    }
    write(root / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["model", "case_count", "passed", "pass_rate", "elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
