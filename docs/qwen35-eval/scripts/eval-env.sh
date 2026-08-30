#!/bin/bash
# 评测指标采集（在每次评测前后调用）
# 用法: source eval-env.sh && snapshot_mem <label>
PORT=8090
RESULTS=~/llm-models/qwen35-eval/results

# 从 llama-server /metrics 拿 token/速度指标（llama.cpp 暴露 prometheus）
snapshot_mem() {
  local label="$1"
  local mem=$(ps -Ao rss,comm | awk '/llama-server/{s+=$1} END{printf "%.2f", s/1048576}')
  local swap=$(sysctl -n vm.swapusage 2>/dev/null | awk -F'used = ' '{print $2}' | awk '{printf "%.2f", $1/1073741824}')
  local total=$(sysctl -n hw.memsize | awk '{printf "%.1f", $1/1073741824}')
  echo "[$label] llama-server RSS=${mem}GiB swap_used=${swap}GiB total_ram=${total}GiB"
  echo "[$label] llama-server RSS=${mem}GiB swap_used=${swap}GiB" >> "$RESULTS/mem.log"
}

# llama.cpp 单请求 timing 从响应头拿：x-prompt-tokens / x-prompt-ms / x-tokens / x-ms
# 完整链路计时与 TTFT 由 eval-run 脚本用 curl -w 采集
