#!/usr/bin/env python3
"""Fish S2 follow-up executor.

Runs in the DEPLOY venv (so mlx / mlx_speech / numpy are importable) and
executes the queue described by the prepared manifest. The 27B Agent should
never call this directly; the launch script invokes it in a separate process
group. The runner writes a per-clip JSONL log and emits a status.json update
when it finishes.

Design contract:
  * No streaming, no LLM, no port-binding.
  * Fish generation runs first; ASR runs only after Fish exits.
  * Any exception is captured and reflected in status.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any

# Locate repo root from the script path.
ROOT = Path(__file__).resolve().parents[1]

DEPLOY = Path("/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local")
DEPLOY_PYTHON = DEPLOY / ".venv" / "bin" / "python"
DEPLOY_TTS = DEPLOY / "scripts" / "tts.py"
DEPLOY_ASR = DEPLOY / "scripts" / "verify_audio.py"

GENERATION_TIMEOUT_S = 180.0
ASR_TIMEOUT_S = 120.0
HEARTBEAT_INTERVAL_S = 5.0


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat()


def write_atomic(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(content, str):
        tmp.write_text(content, encoding="utf-8")
    else:
        tmp.write_bytes(content)
    os.replace(tmp, path)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def load_status(run_id: str) -> dict:
    p = ROOT / "results" / run_id / "status.json"
    return json.loads(p.read_text(encoding="utf-8"))


def save_status(run_id: str, status: dict) -> None:
    status["updated_at"] = now_iso()
    write_atomic(ROOT / "results" / run_id / "status.json",
                 json.dumps(status, ensure_ascii=False, indent=2) + "\n")


def update_status(run_id: str, **fields) -> None:
    s = load_status(run_id)
    s.update(fields)
    save_status(run_id, s)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Baseline validation
# --------------------------------------------------------------------------- #

def collect_baseline(run_id: str, duration_s: float = 60.0,
                     interval_s: float = 2.0) -> dict[str, Any]:
    """Sample system state for `duration_s` before declaring the run ready."""
    import psutil
    samples: list[dict[str, Any]] = []
    log_path = ROOT / "results" / run_id / "logs" / "baseline.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        sample = {"time": now_iso()}
        try:
            vm = psutil.virtual_memory()
            sample["available_gib"] = round(vm.available / (1024 ** 3), 3)
            sample["free_percent"] = round(vm.available / vm.total * 100, 3) if vm.total else None
        except Exception as exc:  # noqa: BLE001
            sample["psutil_error"] = str(exc)
        try:
            swap_text = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True, timeout=2)
            used = None
            for line in swap_text.splitlines():
                if "used" in line and "=" in line:
                    val = line.split("=", 1)[1].strip().split()[0]
                    try:
                        n = float(val)
                        if val.endswith("M"):
                            used = round(n / 1024, 3)
                        elif val.endswith("G"):
                            used = round(n, 3)
                        else:
                            used = round(n / (1024 * 1024), 3)
                    except ValueError:
                        used = None
            sample["swap_used_gib"] = used
        except Exception as exc:  # noqa: BLE001
            sample["swap_sysctl_error"] = str(exc)
        try:
            mp = subprocess.check_output(["memory_pressure", "-Q"], text=True, timeout=3)
            for line in mp.splitlines():
                if "System-wide memory free percentage" in line:
                    try:
                        sample["memory_pressure_free_percent"] = float(line.rsplit(":", 1)[1].strip().rstrip("%"))
                    except (IndexError, ValueError):
                        sample["memory_pressure_free_percent"] = None
                    break
        except Exception as exc:  # noqa: BLE001
            sample["memory_pressure_error"] = str(exc)
        append_jsonl(log_path, sample)
        samples.append(sample)
        time.sleep(interval_s)
    return {
        "samples": len(samples),
        "log": str(log_path),
        "swap_used_gib_max": max((s.get("swap_used_gib") for s in samples if s.get("swap_used_gib") is not None), default=None),
        "available_gib_min": min((s.get("available_gib") for s in samples if s.get("available_gib") is not None), default=None),
        "memory_pressure_free_percent_min": min(
            (s.get("memory_pressure_free_percent") for s in samples if s.get("memory_pressure_free_percent") is not None),
            default=None),
    }


def check_external_load(run_id: str) -> dict[str, Any]:
    """Snapshot external processes that might re-load a large model.

    The plan forbids using pkill or global kill; we only OBSERVE.
    """
    import psutil
    suspicious_keywords = ("llama", "qwen", "fish", "mlx", "vllm", "comfy", "sdxl")
    tracked: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        lname = (proc.info.get("name") or "").lower()
        if any(k in lname or k in cmdline.lower() for k in suspicious_keywords):
            tracked.append({"pid": proc.info["pid"], "name": proc.info["name"], "cmdline": cmdline[:300]})
    log_path = ROOT / "results" / run_id / "logs" / "external-load.jsonl"
    append_jsonl(log_path, {"time": now_iso(), "tracked": tracked})
    return {"tracked": tracked, "log": str(log_path)}


# --------------------------------------------------------------------------- #
# Fish generation
# --------------------------------------------------------------------------- #

def run_fish(run_id: str, manifest: dict[str, Any], queue: list[dict[str, Any]],
             t5_template: dict[str, Any], t5_min_active_minutes: float,
             t5_max_total_tasks: int, run_dir: Path) -> dict[str, Any]:
    """Invoke the DEPLOY tts.py via subprocess for each clip.

    We use a subprocess per clip so we can re-import fresh state per attempt and
    keep the per-clip timeout clean. A single persistent process is also
    supported via the inner_fish mode but is not used here.
    """
    import yaml
    matrix = yaml.safe_load((run_dir / "config" / "test-matrix.yaml").read_text(encoding="utf-8"))

    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    fish_log = run_dir / "logs" / "fish-runner.jsonl"

    completed: list[str] = []
    failed: list[str] = []
    counters = {g: 0 for g in matrix["cases"]}

    # T5 padding: how many clips to insert to satisfy >=30 min active.
    # We estimate per-clip generation time from T1 average; if no data yet,
    # use the plan's 28 s conservative estimate and re-evaluate after each clip.
    est_seconds_per_clip = 28.0
    active_seconds_so_far = 0.0
    target_active_seconds = t5_min_active_minutes * 60.0
    max_total_tasks = t5_max_total_tasks
    inserted_t5 = 0
    insufficient_duration = False

    # The CLI's build_execution_order already placed T4 anchors at:
    #   - position 0..2 : T4 start (3)
    #   - in the middle  : T4 middle (3) (after T3)
    #   - end            : NOT in queue yet, appended at runtime below
    flat = list(queue)
    end_anchor = [c for c in matrix["cases"]["T4"]["clips"] if c["position_in_run"] == "end"]

    # We will append T5 padding until active_seconds_so_far >= target_active_seconds
    # OR until total tasks exceed max_total_tasks (less anchors already in queue).
    total_base_tasks = len(flat)
    t5_active_ceiling = max_total_tasks - total_base_tasks - len(end_anchor)

    def make_padding(index: int) -> dict:
        clip = dict(t5_template)
        clip["case_id"] = f"T5_padding_{index:03d}"
        clip["position"] = -1  # to be reassigned
        return clip

    # --- helpers (defined before the main loop so they are reachable) -------

    def _last_record(path, predicate):
        try:
            for line in reversed(path.read_text(encoding="utf-8").splitlines()):
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if predicate(r):
                    return r
        except FileNotFoundError:
            return None
        return None

    def run_clip(clip: dict) -> None:
        nonlocal active_seconds_so_far
        clip_id = clip["case_id"]
        out_path = audio_dir / f"{clip_id}.wav"
        role_id = clip.get("role_id")
        reference_audio = clip.get("reference_audio")
        per_clip_log = run_dir / "logs" / f"clip-{clip_id}.jsonl"

        # Branch 1: no-reference clips (T0_basic_zh, T0_speaker_tags_experimental).
        # Scene-file mode requires voices[voice] to exist; use --text instead.
        if role_id is None or reference_audio is None:
            cmd = [
                str(DEPLOY_PYTHON), str(DEPLOY_TTS),
                "--text", clip["text"],
                "--output", str(out_path),
                "--seed", str(clip["seed"]),
                "--max-new-tokens", str(clip["max_new_tokens"]),
                "--log", str(per_clip_log),
            ]
        else:
            # Branch 2: reference-conditioned clip via scene-file (one voice, one line).
            scene = {
                "voices": {
                    role_id: {
                        "audio": reference_audio,
                        "text": clip.get("reference_text") or clip["text"],
                    }
                },
                "lines": [{"voice": role_id, "text": clip["text"]}],
            }
            scene_path = audio_dir / f".scene-{clip_id}.json"
            scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
            cmd = [
                str(DEPLOY_PYTHON), str(DEPLOY_TTS),
                "--scene-file", str(scene_path),
                "--output", str(out_path),
                "--seed", str(clip["seed"]),
                "--max-new-tokens", str(clip["max_new_tokens"]),
                "--log", str(per_clip_log),
            ]

        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=GENERATION_TIMEOUT_S + 30)
        elapsed = time.monotonic() - started
        active_seconds_so_far += elapsed
        ok = proc.returncode == 0 and out_path.exists()
        row: dict[str, Any] = {
            "event": "fish_clip_finished",
            "time": now_iso(),
            "case_id": clip_id,
            "group": clip["group"],
            "role_id": role_id,
            "seed": clip["seed"],
            "max_new_tokens": clip["max_new_tokens"],
            "exit_code": proc.returncode,
            "ok": ok,
            "elapsed_seconds": round(elapsed, 3),
            "config_hash": clip.get("config_hash"),
            "input_hash": clip.get("input_hash"),
            "reference_hash": clip.get("reference_hash"),
        }
        if not ok:
            row["stderr_tail"] = proc.stderr[-500:]
            row["stdout_tail"] = proc.stdout[-500:]
        append_jsonl(fish_log, row)
        # Append the inner clip record (per_clip_log) merged into fish_log.
        if per_clip_log.exists():
            for line in per_clip_log.read_text(encoding="utf-8").splitlines():
                try:
                    inner = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if inner.get("event") == "generated":
                    inner["case_id"] = clip_id
                    inner["group"] = clip["group"]
                    inner["config_hash"] = clip.get("config_hash")
                    inner["input_hash"] = clip.get("input_hash")
                    inner["reference_hash"] = clip.get("reference_hash")
                    inner["exit_status"] = "ok" if ok else "fail"
                    if ok and out_path.exists():
                        try:
                            inner["output_path"] = str(out_path)
                            inner["output_sha256"] = sha256_file(out_path)
                        except OSError as exc:
                            inner["sha_error"] = str(exc)
                    append_jsonl(fish_log, inner)
        # Cleanup the helper scene file but keep the log.
        if role_id is not None and reference_audio is not None:
            try:
                (audio_dir / f".scene-{clip_id}.json").unlink()
            except FileNotFoundError:
                pass

    def completed_or_failed(clip, counters, completed, failed):
        counters[clip["group"]] = counters.get(clip["group"], 0) + 1
        last = _last_record(fish_log, lambda r: r.get("case_id") == clip["case_id"]
                            and r.get("event") == "fish_clip_finished")
        if last and last.get("ok"):
            completed.append(clip["case_id"])
        else:
            failed.append(clip["case_id"])
        save_status(run_id, {**load_status(run_id),
                             "completed_case_ids": completed,
                             "failed_case_ids": failed,
                             "last_heartbeat_at": now_iso()})

    # Run!
    t0_run = time.monotonic()
    status = load_status(run_id)
    started_at = now_iso()
    save_status(run_id, {**status, "state": "running", "started_wall_at": started_at,
                          "fish_started_wall_at": started_at})
    append_jsonl(fish_log, {"event": "fish_started", "time": started_at,
                            "queue_length": total_base_tasks,
                            "external_load_summary": status.get("external_load_summary")})

    finished_normally = True
    try:
        # We process flat (base) first; then loop inserting T5 padding until
        # either time budget is met or task budget is exhausted.
        base_index = 0
        t5_index = 0
        while base_index < len(flat):
            clip = flat[base_index]
            base_index += 1
            run_clip(clip)
            completed_or_failed(clip, counters, completed, failed)
            if not insufficient_duration and active_seconds_so_far < target_active_seconds and t5_index < t5_active_ceiling:
                # Insert T5 padding right away (don't wait until end of base).
                while active_seconds_so_far < target_active_seconds and t5_index < t5_active_ceiling:
                    pad = make_padding(t5_index + 1)
                    run_clip(pad)
                    completed_or_failed(pad, counters, completed, failed)
                    t5_index += 1
                    inserted_t5 += 1

            # Sanity: stop early if 120-task ceiling reached including anchors.
            if len(completed) + len(failed) + len(end_anchor) >= max_total_tasks:
                insufficient_duration = active_seconds_so_far < target_active_seconds
                break

        if active_seconds_so_far < target_active_seconds:
            insufficient_duration = True

        # End anchor comes after any T5 padding per plan §5.
        for c in end_anchor:
            run_clip(c)
            completed_or_failed(c, counters, completed, failed)

        if active_seconds_so_far < target_active_seconds:
            insufficient_duration = True
    except Exception as exc:  # noqa: BLE001
        finished_normally = False
        append_jsonl(fish_log, {"event": "fish_aborted", "time": now_iso(),
                                "error": repr(exc), "traceback": _safe_traceback()})
    finally:
        append_jsonl(fish_log, {"event": "fish_finished", "time": now_iso(),
                                "completed": len(completed), "failed": len(failed),
                                "active_seconds": round(active_seconds_so_far, 3),
                                "t5_inserted": inserted_t5,
                                "insufficient_duration": insufficient_duration,
                                "fish_wall_seconds": round(time.monotonic() - t0_run, 3)})

    return {
        "completed": completed,
        "failed": failed,
        "active_seconds": active_seconds_so_far,
        "t5_inserted": inserted_t5,
        "insufficient_duration": insufficient_duration,
        "finished_normally": finished_normally,
    }

def _safe_traceback() -> str:
    import traceback
    return traceback.format_exc()


# --------------------------------------------------------------------------- #
# ASR back-check (sequential, after Fish exit)
# --------------------------------------------------------------------------- #

def run_asr(run_id: str, manifest: dict[str, Any], audio_dir: Path,
            log_path: Path) -> dict[str, Any]:
    """Run ASR on each generated audio clip."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    clips = []
    if (log_path.parent / "fish-runner.jsonl").exists():
        for line in (log_path.parent / "fish-runner.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "generated" and rec.get("case_id"):
                clips.append(rec)
    if not clips:
        log_handle.close()
        return {"clips_processed": 0}
    append_jsonl(log_path, {"event": "asr_started", "time": now_iso(), "clips": len(clips)})

    # We use the DEPLOY verify_audio.py script which expects a JSONL with 'event':'generated' rows.
    metrics_jsonl = log_path.parent / "asr-input-metrics.jsonl"
    with metrics_jsonl.open("w", encoding="utf-8") as f:
        for c in clips:
            f.write(json.dumps({
                "event": "generated",
                "name": c["case_id"],
                "text": c["text"],
                "output": c.get("output_path"),
            }, ensure_ascii=False) + "\n")
    cmd = [str(DEPLOY_PYTHON), str(DEPLOY_ASR),
           "--metrics", str(metrics_jsonl),
           "--output", str(log_path.parent / "asr-verification.json")]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ASR_TIMEOUT_S * len(clips) + 60)
        append_jsonl(log_path, {"event": "asr_finished", "time": now_iso(),
                                "exit_code": proc.returncode,
                                "stdout_tail": proc.stdout[-500:],
                                "stderr_tail": proc.stderr[-500:]})
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired as exc:
        append_jsonl(log_path, {"event": "asr_timeout", "time": now_iso(),
                                "stderr_tail": (exc.stderr or "")[-500:] if isinstance(exc.stderr, str) else None})
        ok = False

    # Convert the verify_audio.py output into the analyze-friendly shape.
    if ok and (log_path.parent / "asr-verification.json").exists():
        rows = json.loads((log_path.parent / "asr-verification.json").read_text(encoding="utf-8"))
        for r in rows:
            append_jsonl(log_path, {"event": "asr_transcribed", "time": now_iso(), **r})
        log_handle.close()
        return {"clips_processed": len(rows), "ok": ok}
    log_handle.close()
    return {"clips_processed": 0, "ok": ok}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=["baseline", "fish", "asr", "finalize", "all"],
                        default="all")
    args = parser.parse_args()

    run_id = args.run_id
    run_dir = ROOT / "results" / run_id
    manifest_path = run_dir / "config" / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest missing at {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    import yaml
    matrix = yaml.safe_load((run_dir / "config" / "test-matrix.yaml").read_text(encoding="utf-8"))
    queue = matrix["queue"]

    save_status(run_id, {**load_status(run_id), "state": "running"})

    # Phase: baseline
    if args.phase in ("baseline", "all"):
        save_status(run_id, {**load_status(run_id), "state": "waiting_for_unload",
                              "baseline_started_at": now_iso()})
        baseline = collect_baseline(run_id)
        ext = check_external_load(run_id)
        save_status(run_id, {**load_status(run_id),
                              "baseline_summary": baseline,
                              "external_load_summary": ext,
                              "state": "running",
                              "baseline_completed_at": now_iso()})

    # Phase: fish
    if args.phase in ("fish", "all"):
        t5_settings = matrix["cases"]["T5"]
        fish_result = run_fish(
            run_id, manifest, queue,
            t5_settings["padding_template"],
            float(t5_settings["minimum_active_minutes"]),
            int(t5_settings["maximum_total_generation_tasks"]),
            run_dir,
        )
        if not fish_result.get('finished_normally') or fish_result.get('failed') or not fish_result.get('completed'):
            save_status(run_id, {**load_status(run_id), 'fish_summary': fish_result,
                                 'state': 'failed', 'stop_reason': 'fish_incomplete_or_failed',
                                 'ended_wall_at': now_iso()})
            return 1
        save_status(run_id, {**load_status(run_id),
                              "fish_summary": fish_result,
                              "state": "fish_done"})

    # Phase: asr (after Fish exits)
    if args.phase in ("asr", "all"):
        asr_result = run_asr(run_id, manifest, run_dir / "audio",
                             run_dir / "logs" / "asr-runner.jsonl")
        expected_asr = len(load_status(run_id).get('completed_case_ids', []))
        if not expected_asr or asr_result.get('clips_processed') != expected_asr or asr_result.get('ok') is False:
            save_status(run_id, {**load_status(run_id), 'state': 'failed',
                                 'asr_summary': asr_result, 'stop_reason': 'asr_failed_or_incomplete',
                                 'ended_wall_at': now_iso()})
            return 1
        save_status(run_id, {**load_status(run_id),
                              "asr_summary": asr_result,
                              "state": "asr_done"})

    if args.phase in ("finalize", "all"):
        validation = subprocess.run(
            [str(DEPLOY_PYTHON), str(ROOT/'scripts/fish-s2-followup.py'),
             'analyze', '--run-id', run_id], capture_output=True, text=True)
        if validation.returncode != 0:
            save_status(run_id, {**load_status(run_id), 'state': 'failed',
                                 'stop_reason': 'evidence_validation_failed',
                                 'validation_stderr': validation.stderr[-2000:],
                                 'ended_wall_at': now_iso()})
            return 1
        save_status(run_id, {**load_status(run_id),
                              "state": "awaiting_human_review",
                              "ended_wall_at": now_iso(),
                              "verdict": "pending"})

    return 0


if __name__ == "__main__":
    sys.exit(main())
