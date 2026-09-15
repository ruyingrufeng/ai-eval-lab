#!/usr/bin/env python3
"""Independent resource monitor for the Fish S2 follow-up runs.

Runs as a sidecar process. Samples every 2 s and writes JSONL lines to the
run's `logs/resource-samples.jsonl`. Stops the runner process group when any
plan-defined stop condition trips.

Never imports mlx, mlx_speech, or any model weights.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


SAMPLE_INTERVAL_S = 2.0
THERMAL_INTERVAL_S = 30.0
DISK_FREE_MIN_GIB = 20.0
STOP_SWAP_DELTA_GIB = 2.0
STOP_SWAP_PER_MIN_GIB = 1.0
STOP_MEM_FREE_PCT = 10.0
STOP_MEM_LOW_CONSECUTIVE = 3
STOP_MISSING_FIELD_CONSECUTIVE = 3
HEARTBEAT_TIMEOUT_S = 30.0
REQUIRED_FIELDS = ("available_gib", "swap_used_gib", "memory_pressure_free_percent")


def now_iso() -> str:
    import datetime as dt
    return dt.datetime.now().astimezone().isoformat()


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def parse_memory_pressure(text: str) -> dict[str, Any]:
    """Parse `memory_pressure -Q` output into a structured dict."""
    out: dict[str, Any] = {"raw": text.strip(), "free_percent": None, "state": None}
    for line in text.splitlines():
        if "System-wide memory free percentage" in line:
            try:
                out["free_percent"] = float(line.rsplit(":", 1)[1].strip().rstrip("%"))
            except (IndexError, ValueError):
                out["free_percent"] = None
        elif "The system has" in line or "free percentage" in line:
            # Variant of the one-shot form.
            try:
                out["free_percent"] = float(line.rsplit(":", 1)[1].strip().rstrip("%"))
            except (IndexError, ValueError):
                pass
    if "System-wide memory free percentage" in text and "%" in text:
        out["state"] = "ok" if (out["free_percent"] or 0) > 30 else "yellow"
    return out


def sample_system(baseline: dict[str, float] | None) -> dict[str, Any]:
    """Single resource sample."""
    sample: dict[str, Any] = {"time": now_iso(), "interval_s": SAMPLE_INTERVAL_S}
    # memory_pressure (best-effort).
    try:
        out = subprocess.check_output(["memory_pressure", "-Q"], text=True, timeout=3)
        parsed = parse_memory_pressure(out)
        sample["memory_pressure_raw"] = parsed["raw"]
        sample["memory_pressure_free_percent"] = parsed["free_percent"]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        sample["memory_pressure_raw"] = None
        sample["memory_pressure_free_percent"] = None
        sample["memory_pressure_error"] = str(exc)

    # psutil first for swap (more reliable than sysctl text parsing on macOS).
    try:
        import psutil
        sw = psutil.swap_memory()
        sample["swap_used_gib"] = round(sw.used / (1024 ** 3), 3)
        sample["swap_total_gib"] = round(sw.total / (1024 ** 3), 3)
    except Exception as exc:  # noqa: BLE001
        sample["swap_psutil_error"] = str(exc)
        sample["swap_used_gib"] = None
        sample["swap_total_gib"] = None

    # sysctl vm.swapusage as a secondary source for raw text.
    try:
        swap_text = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True, timeout=2)
        sample["swap_sysctl_raw"] = swap_text.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        sample["swap_sysctl_raw"] = None
        sample["swap_sysctl_error"] = str(exc)

    # vm_stat pages.
    try:
        pages = subprocess.check_output(["vm_stat"], text=True, timeout=2)
        for line in pages.splitlines():
            key = line.split(":", 1)[0].strip()
            value_text = line.split(":", 1)[1].strip().rstrip(".")
            try:
                value = int(value_text)
            except ValueError:
                continue
            sample[f"vm_{key}"] = value
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        sample["vm_stat_error"] = str(exc)

    # psutil for available memory and process info.
    try:
        import psutil
        vm = psutil.virtual_memory()
        sample["available_gib"] = round(vm.available / (1024 ** 3), 3)
        sample["total_gib"] = round(vm.total / (1024 ** 3), 3)
        sample["free_percent_psutil"] = round(vm.available / vm.total * 100, 3) if vm.total else None
    except Exception as exc:  # noqa: BLE001
        sample["psutil_error"] = str(exc)

    # Snapshot per-process RSS for tracked PIDs.
    pids = sample.pop("_pids_to_track", None)
    if pids:
        tracked: dict[str, dict[str, Any]] = {}
        try:
            import psutil
            for label, pid in pids.items():
                try:
                    proc = psutil.Process(pid)
                    mem = proc.memory_info()
                    tracked[label] = {
                        "pid": pid,
                        "rss_gib": round(mem.rss / (1024 ** 3), 3),
                        "cpu_percent": proc.cpu_percent(interval=None),
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    tracked[label] = {"pid": pid, "error": str(exc)}
        except ImportError as exc:
            tracked["_error"] = str(exc)
        sample["tracked_processes"] = tracked

    # Swap delta from baseline.
    if baseline and sample.get("swap_used_gib") is not None:
        sample["swap_delta_from_baseline_gib"] = round(sample["swap_used_gib"] - baseline.get("swap_used_gib", sample["swap_used_gib"]), 3)

    # Disk free on results/ and DEPLOY.
    for label, path in (("results", str(ROOT / "results")), ("deploy", "/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local")):
        try:
            st = os.statvfs(path)
            free_gib = (st.f_bavail * st.f_frsize) / (1024 ** 3)
            sample[f"disk_free_gib_{label}"] = round(free_gib, 3)
        except FileNotFoundError as exc:
            sample[f"disk_free_gib_{label}"] = None
            sample[f"disk_free_error_{label}"] = str(exc)

    # Thermal every 30 s.
    sample["_thermal_tick"] = int(time.time() // THERMAL_INTERVAL_S)
    if not sample.get("_thermal_cached_for_tick"):
        try:
            therm = subprocess.check_output(["pmset", "-g", "therm"], text=True, timeout=3)
            sample["thermal_raw"] = therm.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            sample["thermal_raw"] = None
            sample["thermal_error"] = str(exc)
        sample["_thermal_cached_for_tick"] = sample["_thermal_tick"]

    return sample


def _swap_used_gib(swap_text: str) -> float | None:
    # Parse "used = 1234M".  Falls back to None on failure.
    for line in swap_text.splitlines():
        if "used" in line and "=" in line:
            val = line.split("=", 1)[1].strip().split()[0]
            try:
                num = float(val)
            except ValueError:
                continue
            if val.endswith("M"):
                return round(num / 1024, 3)
            if val.endswith("G"):
                return round(num, 3)
            return round(num / (1024 * 1024), 3)
    return None


def evaluate_stops(samples: list[dict[str, Any]], baseline: dict[str, float] | None,
                   start_wall: float, runner_pid: int | None) -> str | None:
    """Return a stop reason if any plan-defined threshold trips, else None."""
    if not samples:
        return None
    latest = samples[-1]

    # Disk.
    for label in ("results", "deploy"):
        v = latest.get(f"disk_free_gib_{label}")
        if v is not None and v < DISK_FREE_MIN_GIB:
            return f"disk_free_below_{DISK_FREE_MIN_GIB}gib_on_{label}"

    # Memory pressure below threshold for N consecutive samples.
    pcts = [s.get("memory_pressure_free_percent") for s in samples[-STOP_MEM_LOW_CONSECUTIVE:]]
    pcts = [p for p in pcts if isinstance(p, (int, float))]
    if len(pcts) == STOP_MEM_LOW_CONSECUTIVE and all(p < STOP_MEM_FREE_PCT for p in pcts):
        return f"memory_free_percent_below_{STOP_MEM_FREE_PCT}_consecutive_{STOP_MEM_LOW_CONSECUTIVE}"

    # Swap delta vs baseline.
    if baseline is not None:
        delta = latest.get("swap_delta_from_baseline_gib")
        if isinstance(delta, (int, float)) and delta > STOP_SWAP_DELTA_GIB:
            return f"swap_delta_from_baseline_{delta:.3f}_gib_exceeds_{STOP_SWAP_DELTA_GIB}"

    # Swap growth over rolling 60 s window.
    recent = [s for s in samples if start_wall + (latest.get("_t_rel", 0) - s.get("_t_rel", 0)) <= 60]
    # Equivalent: filter by absolute timestamp fallback to monotonic counter.
    cutoff = time.monotonic() - 60
    recent_60 = [s for s in samples[-120:] if s.get("_t_mono", 0) >= cutoff]
    if len(recent_60) >= 2:
        first = recent_60[0].get("swap_used_gib")
        last = recent_60[-1].get("swap_used_gib")
        if isinstance(first, (int, float)) and isinstance(last, (int, float)):
            if (last - first) > STOP_SWAP_PER_MIN_GIB:
                return f"swap_growth_{last - first:.3f}_gib_in_60s_exceeds_{STOP_SWAP_PER_MIN_GIB}"

    return None


def write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runner-pid", type=int, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=SAMPLE_INTERVAL_S)
    args = parser.parse_args()

    project_results = ROOT / "results" / args.run_id
    logs_dir = project_results / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    resource_log = logs_dir / "resource-samples.jsonl"
    heartbeat_path = logs_dir / "monitor-heartbeat.json"
    stop_marker = logs_dir / "monitor-stop.json"

    # Open the console log for this monitor process.
    console = args.stdout_log.open("a", encoding="utf-8")

    samples: list[dict[str, Any]] = []
    baseline_swap: float | None = None
    stop_reason: str | None = None
    start_mono = time.monotonic()
    next_tick = start_mono
    # Track pid presence.
    runner_pid = args.runner_pid

    def cleanup_and_exit(reason: str) -> None:
        nonlocal stop_reason
        stop_reason = reason
        stop_payload = {"stopped_at": now_iso(), "reason": reason,
                        "samples": len(samples),
                        "runner_pid": runner_pid}
        write_atomic(stop_marker, json.dumps(stop_payload, ensure_ascii=False, indent=2) + "\n")
        print(f"[monitor] stop reason: {reason}", file=console, flush=True)
        # Best-effort signal to runner.
        try:
            os.killpg(runner_pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    def handle_signal(signum, frame):  # noqa: ARG001
        cleanup_and_exit(f"signal_{signum}")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        while True:
            now_mono = time.monotonic()
            if now_mono < next_tick:
                time.sleep(min(0.1, next_tick - now_mono))
                continue
            t_rel = now_mono - start_mono
            sample = sample_system({"swap_used_gib": baseline_swap} if baseline_swap is not None else None)
            sample["_t_rel"] = round(t_rel, 3)
            sample["_t_mono"] = now_mono
            sample["runner_pid"] = runner_pid

            # Detect baseline (first 60 s).
            if baseline_swap is None and samples and len(samples) >= 30:
                baseline_swap = sample.get("swap_used_gib") or baseline_swap

            samples.append(sample)
            append_jsonl(resource_log, sample)
            write_heartbeat(heartbeat_path, {
                "last_sample_at": sample["time"],
                "sample_count": len(samples),
                "runner_pid": runner_pid,
                "baseline_swap_used_gib": baseline_swap,
            })

            # Required field protection.
            miss_counts = sum(1 for s in samples[-STOP_MISSING_FIELD_CONSECUTIVE:]
                              if any(s.get(f) is None for f in REQUIRED_FIELDS))
            if miss_counts >= STOP_MISSING_FIELD_CONSECUTIVE * len(REQUIRED_FIELDS) // 2:
                cleanup_and_exit("required_resource_fields_missing_consecutive")
                break

            # Stop conditions.
            reason = evaluate_stops(samples, {"swap_used_gib": baseline_swap} if baseline_swap is not None else None,
                                    start_mono, runner_pid)
            if reason:
                cleanup_and_exit(reason)
                break

            # Heartbeat protection: if runner pid is gone, exit.
            if runner_pid and not _pid_alive(runner_pid):
                cleanup_and_exit("runner_process_exited")
                break

            next_tick += args.interval
    finally:
        console.close()
    return 0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


if __name__ == "__main__":
    sys.exit(main())
