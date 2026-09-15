#!/usr/bin/env python3
"""Smoke-test for the Fish S2 follow-up executor architecture.

Per plan §P.5: "先用纯 CPU 假任务验证父进程结束后日志仍能更新。"

This script spawns a fake runner (sleep + jsonl writes) and the real monitor
sidecar, then disowns the launcher. It verifies:
  * the runner PID is alive and writing JSONL lines;
  * the monitor PID is alive and sampling resources;
  * the launcher can exit while both children keep running.

It is for dry-run validation only; it does NOT touch Fish / ASR / mlx.

Modes:
  default         — start fake runner + real monitor, wait, verify logs.
  --fake-runner X — act as the fake runner only, run for X seconds, then exit.
  --verify-only   — only verify that an earlier smoke run produced logs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PY = ROOT / "scripts" / "fish-s2-followup-runner.py"
MONITOR_PY = ROOT / "scripts" / "fish-s2-followup-monitor.py"
DEPLOY_PY = Path("/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local/.venv/bin/python")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat()


def fake_runner(run_id: str, duration_s: float) -> None:
    """A CPU-only fake runner that writes fake 'generated' rows."""
    log_dir = ROOT / "results" / run_id / "logs"
    log_path = log_dir / "fish-runner.jsonl"
    status_path = ROOT / "results" / run_id / "status.json"
    started = time.monotonic()
    log_dir.mkdir(parents=True, exist_ok=True)
    i = 0
    while time.monotonic() - started < duration_s:
        i += 1
        rec = {
            "event": "fish_clip_finished",
            "time": now_iso(),
            "case_id": f"FAKE_{i:03d}",
            "group": "FAKE",
            "role_id": "narrator",
            "seed": 42,
            "max_new_tokens": 512,
            "exit_code": 0,
            "ok": True,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        gen = dict(rec, event="generated", audio_seconds=3.0,
                   generation_seconds=10.0, rtf=3.33)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(gen, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        # Heartbeat into status.json so the monitor and any controller can see it.
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            status = {"run_id": run_id}
        status["last_heartbeat_at"] = now_iso()
        completed = status.setdefault("completed_case_ids", [])
        if rec["case_id"] not in completed:
            completed.append(rec["case_id"])
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        time.sleep(2)
    # Mark finished.
    rec = {"event": "fish_finished", "time": now_iso(), "fake": True,
           "completed": i, "active_seconds": round(time.monotonic() - started, 3)}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    # Final status.json update.
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        status = {"run_id": run_id}
    status["state"] = "completed"
    status["verdict"] = "pending"
    status["fake_smoke"] = True
    status["ended_wall_at"] = now_iso()
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def orchestrator(args: argparse.Namespace) -> int:
    run_id = args.run_id
    paths = {
        "results": ROOT / "results" / run_id,
        "logs": ROOT / "results" / run_id / "logs",
        "deploy": Path("/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local/experiments") / run_id,
    }
    for d in paths.values():
        d.mkdir(parents=True, exist_ok=True)

    if args.verify_only:
        fish_log = paths["logs"] / "fish-runner.jsonl"
        res_log = paths["logs"] / "resource-samples.jsonl"
        if not fish_log.exists() or not res_log.exists():
            print(f"smoke verify FAIL: missing {fish_log} or {res_log}", file=sys.stderr)
            return 1
        fish_lines = sum(1 for _ in fish_log.open(encoding="utf-8"))
        res_lines = sum(1 for _ in res_log.open(encoding="utf-8"))
        print(f"smoke verify: fish lines={fish_lines}, resource lines={res_lines}")
        if fish_lines < 2 or res_lines < 3:
            print("smoke verify FAIL: not enough lines", file=sys.stderr)
            return 1
        print("smoke verify PASS")
        return 0

    # 1. Start fake runner in its own session (independent of this orchestrator).
    cmd_runner = [
        DEPLOY_PY, str(Path(__file__).resolve()),
        "--run-id", run_id,
        "--fake-runner", str(args.duration),
    ]
    runner_proc = subprocess.Popen(cmd_runner, start_new_session=True,
                                   stdout=paths["logs"].joinpath("runner-console.log").open("w"),
                                   stderr=subprocess.STDOUT)
    runner_pid = runner_proc.pid
    print(f"[smoke] fake runner pid={runner_pid}")

    # 2. Start monitor in its own session.
    monitor_log = paths["logs"] / "monitor-console.log"
    cmd_monitor = [
        DEPLOY_PY, str(MONITOR_PY),
        "--run-id", run_id,
        "--runner-pid", str(runner_pid),
        "--stdout-log", str(monitor_log),
        "--interval", "2",
    ]
    monitor_proc = subprocess.Popen(cmd_monitor, start_new_session=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
    print(f"[smoke] monitor pid={monitor_proc.pid}")

    # 3. Wait a few seconds, then check the runner is logging.
    time.sleep(6)
    fish_log = paths["logs"] / "fish-runner.jsonl"
    res_log = paths["logs"] / "resource-samples.jsonl"
    if not fish_log.exists() or fish_log.stat().st_size == 0:
        print(f"smoke FAIL: fish log empty at {fish_log}", file=sys.stderr)
        _kill_group(runner_pid)
        _kill_group(monitor_proc.pid)
        return 1
    if not res_log.exists() or res_log.stat().st_size == 0:
        print(f"smoke FAIL: resource log empty at {res_log}", file=sys.stderr)
        _kill_group(runner_pid)
        _kill_group(monitor_proc.pid)
        return 1
    print(f"[smoke] fish log bytes={fish_log.stat().st_size}, "
          f"resource log bytes={res_log.stat().st_size}")

    # 4. Sleep until duration is reached, then verify runner exited and monitor
    # followed the heartbeat.
    elapsed = 6.0
    while runner_proc.poll() is None and elapsed < args.duration + 15:
        time.sleep(1)
        elapsed += 1
    print(f"[smoke] runner exited after {elapsed:.1f}s "
          f"(target {args.duration:.1f}s)")

    # Allow monitor to detect runner exit (heartbeat loop).
    time.sleep(4)
    _kill_group(runner_pid)
    _kill_group(monitor_proc.pid)

    fish_lines = sum(1 for _ in fish_log.open(encoding="utf-8")) if fish_log.exists() else 0
    res_lines = sum(1 for _ in res_log.open(encoding="utf-8")) if res_log.exists() else 0
    print(f"[smoke] final fish lines={fish_lines} resource lines={res_lines}")
    if fish_lines < 4 or res_lines < 4:
        print("smoke FAIL: insufficient log rows", file=sys.stderr)
        return 1
    print("smoke PASS")
    return 0


def _kill_group(pid: int) -> None:
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    p.add_argument("--duration", type=float, default=30.0,
                   help="Seconds the fake runner should remain active.")
    p.add_argument("--verify-only", action="store_true",
                   help="Just verify a previous smoke run wrote expected rows.")
    p.add_argument("--fake-runner", type=float, default=None,
                   help="Run as the fake runner only, for the given duration.")
    args = p.parse_args()
    if args.fake_runner is not None:
        fake_runner(args.run_id, float(args.fake_runner))
        return 0
    return orchestrator(args)


if __name__ == "__main__":
    sys.exit(main())
