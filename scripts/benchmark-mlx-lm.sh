#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: $0 MODEL_ID [PROMPT]" >&2
  exit 2
fi

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin="$project_root/.venv/mlx-lm/bin/python"
model_id=$1
prompt=${2:-'请用三句话说明本地模型基准测试为什么需要固定版本、参数和随机种子。'}
timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
output_dir="$project_root/results/text/$timestamp"

if [ ! -x "$python_bin" ]; then
  echo "MLX LM environment missing; run scripts/setup-mlx-lm.sh first" >&2
  exit 1
fi

mkdir -p "$output_dir"
{
  echo "timestamp_utc=$timestamp"
  echo "model=$model_id"
  echo "command=mlx_lm.generate"
} > "$output_dir/metadata.txt"

"$python_bin" -m mlx_lm.generate \
  --model "$model_id" \
  --prompt "$prompt" \
  --max-tokens 256 \
  --seed 42 \
  2>&1 | tee "$output_dir/run.log"

printf '%s\n' "$output_dir"
