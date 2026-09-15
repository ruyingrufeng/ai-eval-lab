#!/bin/bash
# Independent launcher for the Fish S2 Pro follow-up benchmark.
# Run this from a separate terminal after the 27B model has been unloaded.
#
# Usage:  ./scripts/start-fish-s2-followup.sh <run-id>
#
# Side effects:
#   * Spawns the resource monitor in its own session.
#   * Spawns the runner in its own session (independent of any caller shell).
#   * Returns the runner PID so the user can `kill -TERM -<pid>` the whole group.
#
# This script never blocks the Agent; it returns once both processes are running
# and the manifest has been re-validated.
#
# Note: macOS does not always ship the `setsid` binary, so we use Python's
# `os.setsid()` syscall via subprocess.Popen(start_new_session=True).

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <run-id>" >&2
  exit 1
fi

RUN_ID="$1"
PROJECT_ROOT="${PROJECT_ROOT:-/Users/jacky/Library/Mobile Documents/com~apple~CloudDocs/AI 项目/内容工厂管理}"
DEPLOY="${FISH_S2_DEPLOY:-/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local}"
DEPLOY_PY="$DEPLOY/.venv/bin/python"
RUNNER="$PROJECT_ROOT/scripts/fish-s2-followup-runner.py"
MONITOR="$PROJECT_ROOT/scripts/fish-s2-followup-monitor.py"
LOG_DIR="$PROJECT_ROOT/results/$RUN_ID/logs"
STATUS_FILE="$PROJECT_ROOT/results/$RUN_ID/status.json"
MANIFEST="$PROJECT_ROOT/results/$RUN_ID/config/manifest.json"
RUNNER_LOG="$LOG_DIR/runner-console.log"
MONITOR_LOG="$LOG_DIR/monitor-console.log"

# ---------------------------------------------------------------------------
# Pre-flight: prepared manifest exists, no model preload, status is sane.
# ---------------------------------------------------------------------------
if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: manifest missing at $MANIFEST — run prepare + check first." >&2
  exit 1
fi

if [ ! -x "$DEPLOY_PY" ]; then
  echo "ERROR: deploy python missing: $DEPLOY_PY" >&2
  exit 1
fi

if [ ! -f "$RUNNER" ] || [ ! -f "$MONITOR" ]; then
  echo "ERROR: runner/monitor scripts missing." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

echo "[launch] $RUN_ID starting at $(date '+%Y-%m-%dT%H:%M:%S%z')"
echo "[launch] deploy:        $DEPLOY"
echo "[launch] runner:        $RUNNER"
echo "[launch] monitor:       $MONITOR"
echo "[launch] status file:   $STATUS_FILE"

# Re-validate before launch (cheap; does NOT load models).
"$DEPLOY_PY" "$PROJECT_ROOT/scripts/fish-s2-followup.py" check --run-id "$RUN_ID"

# Stamp the launching state.
PYTHONPATH="$PROJECT_ROOT" "$DEPLOY_PY" - "$RUN_ID" <<'EOF'
import json, os, sys, time
from pathlib import Path
run_id = sys.argv[1]
status_path = Path("/Users/jacky/Library/Mobile Documents/com~apple~CloudDocs/AI 项目/内容工厂管理/results") / run_id / "status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status["state"] = "running"
status["launched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
status["launched_by"] = os.environ.get("USER", "unknown")
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF

# ---------------------------------------------------------------------------
# Spawn the runner in its own session via Python (setsid() syscall).
# The python helper waits for the runner to write its PID file, then exits.
# ---------------------------------------------------------------------------
SPAWN_PY="$LOG_DIR/_spawn.py"
cat > "$SPAWN_PY" <<PYEOF
import os, subprocess, sys, time
from pathlib import Path

run_id = sys.argv[1]
runner_log = sys.argv[2]
monitor_log = sys.argv[3]
log_dir = Path(sys.argv[4])

# Spawn the runner in a brand-new session so it survives this launcher.
runner_cmd = [sys.argv[5], sys.argv[6], "--run-id", run_id, "--phase", "all"]
runner_log_f = open(runner_log, "a")
runner_proc = subprocess.Popen(
    runner_cmd,
    stdout=runner_log_f,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
    close_fds=True,
)
runner_pid = runner_proc.pid
(log_dir / "runner.pid").write_text(str(runner_pid) + "\n", encoding="utf-8")
print(f"[spawn] runner pid={runner_pid}", flush=True)

# Wait until the runner either writes a "fish_started" event to its log or
# exits too quickly (error case).
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    fish_log = log_dir / "fish-runner.jsonl"
    if fish_log.exists() and fish_log.stat().st_size > 0:
        break
    if runner_proc.poll() is not None:
        # Crashed before logging.
        print(f"[spawn] runner exited prematurely with code {runner_proc.returncode}", flush=True)
        break
    time.sleep(1)

if runner_proc.poll() is not None:
    sys.exit(1)
sys.exit(0)
PYEOF

"$DEPLOY_PY" "$SPAWN_PY" \
    "$RUN_ID" \
    "$RUNNER_LOG" \
    "$MONITOR_LOG" \
    "$LOG_DIR" \
    "$DEPLOY_PY" \
    "$RUNNER"

RUNNER_PID=$(cat "$LOG_DIR/runner.pid")
echo "[launch] runner pid:    $RUNNER_PID"

# Update status.json with the runner PID.
"$DEPLOY_PY" - "$RUN_ID" "$RUNNER_PID" <<'EOF'
import json, os, sys, time
from pathlib import Path
run_id, runner_pid = sys.argv[1], int(sys.argv[2])
status_path = Path("/Users/jacky/Library/Mobile Documents/com~apple~CloudDocs/AI 项目/内容工厂管理/results") / run_id / "status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status.setdefault("process_ids", {})["runner"] = runner_pid
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF

# ---------------------------------------------------------------------------
# Spawn the monitor in its own session.
# ---------------------------------------------------------------------------
MON_SPAWN_PY="$LOG_DIR/_spawn_monitor.py"
cat > "$MON_SPAWN_PY" <<PYEOF
import os, subprocess, sys, time
from pathlib import Path

run_id = sys.argv[1]
runner_pid = int(sys.argv[2])
monitor_log = sys.argv[3]
log_dir = Path(sys.argv[4])

monitor_cmd = [sys.argv[5], sys.argv[6],
               "--run-id", run_id,
               "--runner-pid", str(runner_pid),
               "--stdout-log", monitor_log,
               "--interval", "2"]
mon_log_f = open(monitor_log, "a")
mon_proc = subprocess.Popen(
    monitor_cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
    close_fds=True,
)
mon_pid = mon_proc.pid
(log_dir / "monitor.pid").write_text(str(mon_pid) + "\n", encoding="utf-8")
print(f"[spawn] monitor pid={mon_pid}", flush=True)
sys.exit(0)
PYEOF

"$DEPLOY_PY" "$MON_SPAWN_PY" \
    "$RUN_ID" \
    "$RUNNER_PID" \
    "$MONITOR_LOG" \
    "$LOG_DIR" \
    "$DEPLOY_PY" \
    "$MONITOR"

MONITOR_PID=$(cat "$LOG_DIR/monitor.pid")
echo "[launch] monitor pid:   $MONITOR_PID"

"$DEPLOY_PY" - "$RUN_ID" "$MONITOR_PID" <<'EOF'
import json, sys
from pathlib import Path
run_id, monitor_pid = sys.argv[1], int(sys.argv[2])
status_path = Path("/Users/jacky/Library/Mobile Documents/com~apple~CloudDocs/AI 项目/内容工厂管理/results") / run_id / "status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status.setdefault("process_ids", {})["monitor"] = monitor_pid
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF

echo "[launch] ready. To follow progress:"
echo "         tail -F $LOG_DIR/runner-console.log"
echo "         tail -F $LOG_DIR/monitor-console.log"
echo "         tail -F $LOG_DIR/fish-runner.jsonl"
echo "         tail -F $LOG_DIR/resource-samples.jsonl"
echo "         tail -F $LOG_DIR/asr-runner.jsonl"
echo
echo "[launch] To stop the whole run safely:"
echo "         kill -TERM $RUNNER_PID    # runner first"
echo "         kill -TERM $MONITOR_PID   # then monitor"
echo
echo "[launch] Run ID: $RUN_ID"
