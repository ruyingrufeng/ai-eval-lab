#!/bin/bash
# Qwen3.5-9B 评测服务（独立端口 8090，不干扰 8086/8088）
# 按独立评测方案配置：Metal 全量 / slot 1 / KV Q8+Q8 / ctx 131072 / temp 0.6 / top_p 0.9
MODEL=~/llm-models/Qwen3.5-9B-Q4_K.gguf
PORT=8090

if ! [ -f "$MODEL" ]; then
  echo "模型不存在: $MODEL（还在下载？）"; exit 1
fi

if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/health"; then
  echo "服务已在运行: port $PORT"; exit 0
fi

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
exec /opt/homebrew/Cellar/llama.cpp/10470/bin/llama-server \
  -m "$MODEL" \
  --host 127.0.0.1 --port "$PORT" \
  -c 65536 --parallel 1 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --temp 0.6 --top-p 0.9 \
  -ngl 99 \
  --no-webui \
  --log-file ~/llm-models/qwen35-eval/results/llama-server.log
