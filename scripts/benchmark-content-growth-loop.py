#!/usr/bin/env python3
"""Run the first end-to-end business Agent benchmark through Hermes."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {flatten_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    return str(value)


def setup_workspace(config: dict[str, Any], workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    shared = config["shared_case"]
    brief = f"""# 项目 Brief

- 账号：{shared['account']}
- 平台：{shared['platform']}
- 受众：{shared['audience']}
- 业务目标：{shared['business_goal']}

本任务只允许使用 inputs/ 中的固定资料，不得访问网络，不得补充外部事实。
"""
    write(workspace / "inputs/brief.md", brief)
    write(workspace / "inputs/source_facts.json", json.dumps(config["source_facts"], ensure_ascii=False, indent=2) + "\n")
    write(workspace / "inputs/editor_feedback.json", json.dumps(config["editor_feedback"], ensure_ascii=False, indent=2) + "\n")
    write(workspace / "inputs/metric_definitions.json", json.dumps(config["operations_metric_definitions"], ensure_ascii=False, indent=2) + "\n")
    rows = config["operations_records"]
    with (workspace / "inputs/operations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(workspace / "RUN_RULES.md", """# 运行规则

1. 只读 inputs/，只写 outputs/；不得访问任务目录外文件或网络。
2. 不得修改 inputs/、RUN_RULES.md 或 grader。
3. 数字必须用 Python 等确定性工具计算，不得心算后直接填写。
4. 事实、推断和建议必须明确区分。
5. 每阶段完成后自行检查 JSON 可解析、所需文件存在。
""")


def base_prompt(workspace: Path, stage: str) -> str:
    return f"""你正在参加本地语言模型业务 Agent 评测，当前阶段是 {stage}。
唯一允许操作的目录：{workspace}
先阅读 RUN_RULES.md 和 inputs/，再检查 outputs/ 中前序阶段的产物。禁止网络和目录外访问。
只完成本阶段要求；必须真实创建文件并运行本地校验。最终用中文简述产物和验证，不要复述全文。
"""


def prompt_stage_1(workspace: Path) -> str:
    return base_prompt(workspace, "1/4 资料理解与内容策略") + """

创建：
1. outputs/fact_register.json：JSON 数组，逐条保存 inputs/source_facts.json 的全部事实；每项包含 id、fact、planned_use。不得增加外部事实。
2. outputs/content_strategy.md：说明受众需求、文章目标、内容角度、信息优先级、明确不采用的夸张写法。
3. outputs/outline.md：文章提纲，前两段必须优先回答时间、覆盖区域和票价，后续包含换乘、无障碍、小程序信息及出发前检查清单。

使用 Python 校验 fact_register.json 可解析且恰好9项。
"""


def prompt_stage_2(workspace: Path) -> str:
    return base_prompt(workspace, "2/4 写作与改稿") + """

必须沿用 outputs/fact_register.json、content_strategy.md 和 outline.md：
1. 创建 outputs/draft_v1.md，写一篇城市生活类微信公众号文章初稿，只能使用固定资料事实。
2. 阅读 inputs/editor_feedback.json，创建 outputs/draft_v2.md。正文中文字符数必须在900–1300之间；不得把8周试运营写成永久服务；结尾必须是可执行的出发前检查清单。
3. 创建 outputs/revision_log.json：JSON数组，每条编辑意见对应 status、changes、evidence 三个字段，evidence 指向 v2 中的具体标题或短语。

使用 Python 统计 draft_v2.md 中文字符数、检查两个版本不同，并验证 revision_log.json 可解析。
"""


def prompt_stage_3(workspace: Path) -> str:
    return base_prompt(workspace, "3/4 运营数据分析") + """

读取 inputs/operations.csv 与 metric_definitions.json，必须使用 Python 计算，不得改定义。

创建 outputs/metrics.json，严格使用结构：
{
  "aggregate": {
    "impressions": 整数, "views_3s": 整数, "completions": 整数,
    "completion_rate": 小数, "engagement_rate": 小数, "follow_conversion_rate": 小数
  },
  "posts": {
    "A": {"completion_rate": 小数, "engagement_rate": 小数, "follow_conversion_rate": 小数},
    "B": 同上, "C": 同上, "D": 同上
  },
  "weakest_completion_post": "ID",
  "best_follow_conversion_post": "ID"
}

创建 outputs/operations_review.md，分为“观测事实”“假设”“建议验证”三节。不得把相关性写成因果，不得虚构平台算法或受众反馈。运行独立 Python 复算并比较 JSON。
"""


def prompt_stage_4(workspace: Path) -> str:
    return base_prompt(workspace, "4/4 内容增长闭环计划") + """

综合前序文章、修改记录、metrics.json 和 operations_review.md：
1. 创建 outputs/next_cycle_plan.json，结构为 {"experiments": [...]}，恰好4个实验。每项必须包含 id、hypothesis、evidence、content_change、primary_metric、duration、stop_condition。不得承诺具体增长百分比。
2. 创建 outputs/executive_summary.md，向账号负责人说明：本轮文章策略、历史数据最可靠的三个发现、下一轮四条内容如何分工、如何判断继续/停止。明确事实与假设。

至少一个实验借鉴B的公共交通攻略表现，至少一个借鉴D的亲子无障碍表现，至少一个针对C的低完播问题；四条都必须与本次夜游公交内容或其可验证衍生方向相关。使用 Python 校验JSON结构和4个实验字段完整。
"""


FACT_TOKENS = [
    ["9月5日", "8周"], ["N1", "N2"], ["周五", "周六", "19:00", "24:00"],
    ["2元"], ["60分钟", "不重复计费"], ["火车站", "老街", "滨水艺术中心"],
    ["低地板", "轮椅"], ["小程序", "拥挤度"], ["第四周", "调整班次"],
]


def grade_stage_1(workspace: Path) -> dict[str, Any]:
    required = [workspace / "outputs/fact_register.json", workspace / "outputs/content_strategy.md", workspace / "outputs/outline.md"]
    exists = all(p.exists() for p in required)
    try:
        facts = read_json(required[0])
        combined = " ".join(p.read_text(encoding="utf-8") for p in required)
        facts_ok = isinstance(facts, list) and len(facts) == 9 and all(all(token in combined for token in group) for group in FACT_TOKENS)
    except Exception as exc:
        facts_ok, facts = False, str(exc)
    return {"grader_passes": exists and facts_ok, "required_files_exist": exists, "nine_facts_and_tokens_present": facts_ok}


def grade_stage_2(workspace: Path) -> dict[str, Any]:
    paths = [workspace / "outputs/draft_v1.md", workspace / "outputs/draft_v2.md", workspace / "outputs/revision_log.json"]
    exists = all(p.exists() for p in paths)
    try:
        v1, v2 = paths[0].read_text(encoding="utf-8"), paths[1].read_text(encoding="utf-8")
        log = read_json(paths[2])
        count = chinese_chars(v2)
        facts_ok = all(all(token in v2 for token in group) for group in FACT_TOKENS)
        feedback_ok = all(token in v2 for token in ["试运营", "8周", "低地板", "轮椅", "拥挤度", "检查"])
        forbidden = any(token in v2 for token in ["永久免费", "每天运营", "政府补贴", "客流翻倍", "永久运营"])
        log_ok = isinstance(log, list) and len(log) == 4 and all(all(k in x for k in ["status", "changes", "evidence"]) for x in log)
        passed = exists and 900 <= count <= 1300 and v1 != v2 and facts_ok and feedback_ok and not forbidden and log_ok
    except Exception as exc:
        count, facts_ok, feedback_ok, forbidden, log_ok, passed = -1, False, False, False, False, False
    return {"grader_passes": passed, "required_files_exist": exists, "draft_v2_chinese_chars": count, "facts_present": facts_ok, "feedback_addressed": feedback_ok, "forbidden_claim_found": forbidden, "revision_log_valid": log_ok}


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def grade_stage_3(workspace: Path) -> dict[str, Any]:
    metric_path, review_path = workspace / "outputs/metrics.json", workspace / "outputs/operations_review.md"
    exists = metric_path.exists() and review_path.exists()
    expected_posts = {
        "A": (0.5, 0.06, 60 / 7000), "B": (0.7, 0.1075, 0.015),
        "C": (0.3, 440 / 12000, 30 / 7200), "D": (0.7, 0.13, 110 / 4800),
    }
    try:
        data = read_json(metric_path)
        agg = data["aggregate"]
        aggregate_ok = (
            agg["impressions"] == 36000 and agg["views_3s"] == 25000 and agg["completions"] == 13220
            and close(agg["completion_rate"], 0.5288)
            and close(agg["engagement_rate"], 2680 / 36000)
            and close(agg["follow_conversion_rate"], 290 / 25000)
        )
        posts_ok = all(
            close(data["posts"][pid]["completion_rate"], values[0])
            and close(data["posts"][pid]["engagement_rate"], values[1])
            and close(data["posts"][pid]["follow_conversion_rate"], values[2])
            for pid, values in expected_posts.items()
        )
        extrema_ok = data["weakest_completion_post"] == "C" and data["best_follow_conversion_post"] == "D"
        review = review_path.read_text(encoding="utf-8")
        sections_ok = all(x in review for x in ["观测事实", "假设", "建议验证"])
        passed = exists and aggregate_ok and posts_ok and extrema_ok and sections_ok
    except Exception:
        aggregate_ok = posts_ok = extrema_ok = sections_ok = passed = False
    return {"grader_passes": passed, "required_files_exist": exists, "aggregate_ok": aggregate_ok, "per_post_ok": posts_ok, "extrema_ok": extrema_ok, "review_sections_ok": sections_ok}


def grade_stage_4(workspace: Path) -> dict[str, Any]:
    plan_path, summary_path = workspace / "outputs/next_cycle_plan.json", workspace / "outputs/executive_summary.md"
    exists = plan_path.exists() and summary_path.exists()
    try:
        plan = read_json(plan_path)
        experiments = plan["experiments"]
        fields = ["id", "hypothesis", "evidence", "content_change", "primary_metric", "duration", "stop_condition"]
        structure_ok = isinstance(experiments, list) and len(experiments) == 4 and all(all(k in x and str(x[k]).strip() for k in fields) for x in experiments)
        combined = flatten_text(experiments) + " " + summary_path.read_text(encoding="utf-8")
        evidence_ok = all(x in combined for x in ["B", "D", "C", "公共交通", "亲子", "无障碍", "完播"])
        context_ok = all(x in combined for x in ["夜游公交", "试运营"])
        forbidden = bool(re.search(r"(?:提升|增长|提高)\s*\d+(?:\.\d+)?%", combined))
        passed = exists and structure_ok and evidence_ok and context_ok and not forbidden
    except Exception:
        structure_ok = evidence_ok = context_ok = passed = False
        forbidden = False
    return {"grader_passes": passed, "required_files_exist": exists, "four_experiments_valid": structure_ok, "cross_stage_evidence_used": evidence_ok, "workflow_context_retained": context_ok, "invented_growth_prediction_found": forbidden}


STAGES: list[tuple[str, Callable[[Path], str], Callable[[Path], dict[str, Any]]]] = [
    ("understand_and_plan", prompt_stage_1, grade_stage_1),
    ("write_and_revise", prompt_stage_2, grade_stage_2),
    ("analyze_operations", prompt_stage_3, grade_stage_3),
    ("close_the_loop", prompt_stage_4, grade_stage_4),
]


def run_stage(args: argparse.Namespace, root: Path, workspace: Path, stage_id: str, prompt_fn: Callable[[Path], str], grader: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    usage_path = root / "usage" / f"{stage_id}.json"
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = prompt_fn(workspace)
    command = [
        "hermes", "--oneshot", prompt, "--provider", args.provider, "--model", args.model,
        "--toolsets", "terminal,file", "--usage-file", str(usage_path), "--reasoning", "none",
    ]
    start = time.monotonic()
    try:
        env = os.environ.copy()
        if args.hermes_home:
            env["HERMES_HOME"] = str(args.hermes_home.resolve())
        proc = subprocess.run(command, cwd=workspace, text=True, capture_output=True, timeout=args.timeout, env=env)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "timeout")
        timed_out = True
    elapsed = round(time.monotonic() - start, 3)
    grade = grader(workspace)
    usage = read_json(usage_path) if usage_path.exists() else {}
    result = {
        "stage_id": stage_id,
        "elapsed_seconds": elapsed,
        "process_exit_code": proc.returncode,
        "timed_out": timed_out,
        "hard_gate_pass": bool(grade.get("grader_passes")) and not timed_out,
        "grade": grade,
        "usage": usage,
        "final_answer": proc.stdout.strip(),
        "stderr_tail": proc.stderr[-4000:],
    }
    write(root / "stages" / f"{stage_id}.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("benchmarks/agent_business_first_batch.yaml"))
    parser.add_argument("--provider", default="local-fable27b")
    parser.add_argument("--model", default="qwen3.6-27b-fable")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--hermes-home", type=Path, help="Use an isolated Hermes configuration directory")
    parser.add_argument("--resume-workspace", type=Path, help="Copy an existing partial workspace instead of creating a fresh one")
    parser.add_argument("--start-stage", choices=[x[0] for x in STAGES], default=STAGES[0][0])
    parser.add_argument("--max-stages", type=int, help="Limit the number of stages for a gate test")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    if args.resume_workspace:
        source_workspace = args.resume_workspace.resolve()
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(source_workspace, workspace)
    else:
        setup_workspace(config, workspace)
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    results = []
    start_index = next(i for i, stage in enumerate(STAGES) if stage[0] == args.start_stage)
    selected_stages = STAGES[start_index:]
    if args.max_stages is not None:
        selected_stages = selected_stages[:args.max_stages]
    for stage_id, prompt_fn, grader in selected_stages:
        result = run_stage(args, root, workspace, stage_id, prompt_fn, grader)
        results.append(result)
        print(f"{stage_id}: pass={result['hard_gate_pass']} elapsed={result['elapsed_seconds']}s", flush=True)
        if result["timed_out"] or result["process_exit_code"] != 0:
            break
    summary = {
        "schema_version": 1,
        "workflow_id": config["workflow_id"],
        "started_at": started_at,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": args.model,
        "stage_count_planned": len(selected_stages),
        "stage_count_run": len(results),
        "stage_passed": sum(x["hard_gate_pass"] for x in results),
        "workflow_pass": len(results) == len(selected_stages) and all(x["hard_gate_pass"] for x in results),
        "resume_workspace": str(args.resume_workspace.resolve()) if args.resume_workspace else None,
        "start_stage": args.start_stage,
        "hermes_home": str(args.hermes_home.resolve()) if args.hermes_home else None,
        "elapsed_seconds": round(sum(x["elapsed_seconds"] for x in results), 3),
        "stages": results,
    }
    write(root / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["workflow_id", "model", "stage_count_run", "stage_passed", "workflow_pass", "elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
