#!/bin/bash
# Qwen3.5-9B 独立评测自动流水线（launchd 托管，无需人工）
# 阶段：等下载 → 起服务 → 验证 → 评测三阶段 → 上下文 → 报告
EVAL=~/llm-models/qwen35-eval
LOG=$EVAL/results/auto_eval.log
MODEL=~/llm-models/Huihui-Qwen3.5-9B-abliterated.i1-Q5_K_M.gguf
TARGET=6522005152
PORT=8090

log() { echo "[$(date '+%F %T')] $1" >> "$LOG"; }

log "=== AUTO EVAL START ==="

# ---------- 1. 等下载完成（最多 10h） ----------
for i in $(seq 1 600); do
  SZ=$(stat -f%z "$MODEL" 2>/dev/null || echo 0)
  if [ "$SZ" -ge "$TARGET" ]; then
    log "download complete: $SZ bytes"; break
  fi
  if [ $((i % 10)) -eq 0 ]; then log "waiting download... ${SZ} / ${TARGET}"; fi
  sleep 60
done
SZ=$(stat -f%z "$MODEL" 2>/dev/null || echo 0)
if [ "$SZ" -lt "$TARGET" ]; then
  log "FATAL: download not complete after 10h"; exit 1
fi

# ---------- 2. 启动 llama-server ----------
if ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/health"; then
  nohup bash "$EVAL/scripts/start-9b-eval.sh" >> "$LOG" 2>&1 &
  for i in $(seq 1 120); do
    sleep 2
    curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/health" && break
  done
fi
curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/health" || { log "FATAL: llama-server not up"; exit 1; }
log "llama-server up on $PORT"

# ---------- 3. 验证推理 ----------
python3 - <<'EOF' >> "$LOG" 2>&1
import json, urllib.request, time
req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions",
  data=json.dumps({"model":"q","messages":[{"role":"user","content":"说 OK"}],"max_tokens":10}).encode(),
  headers={"Content-Type":"application/json"})
t=time.time()
r = json.load(urllib.request.urlopen(req, timeout=120))
print("SMOKE_TEST:", r["choices"][0]["message"]["content"][:50], f"{time.time()-t:.1f}s")
EOF

# ---------- 4. 评测三阶段 ----------
cd "$EVAL/scripts" || exit 1
log "phase gate..."
python3 eval_all.py gate >> "$LOG" 2>&1 || log "gate phase error"
log "phase long..."
python3 eval_all.py long >> "$LOG" 2>&1 || log "long phase error"
log "phase basic..."
python3 eval_all.py basic >> "$LOG" 2>&1 || log "basic phase error"

# ---------- 5. 上下文压力 ----------
log "ctx phases..."
python3 ctx_eval.py 16k 32k 64k 96k >> "$LOG" 2>&1 || log "ctx phase error"

# ---------- 6. 生成报告 ----------
log "generating report..."
python3 gen_report.py >> "$LOG" 2>&1 || log "report gen error"

log "=== AUTO EVAL DONE ==="
echo "COMPLETE" >> "$LOG"
