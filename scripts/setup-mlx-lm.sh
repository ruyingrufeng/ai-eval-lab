#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
environment_dir="$project_root/.venv/mlx-lm"

python3 -m venv "$environment_dir"
"$environment_dir/bin/python" -m pip install --upgrade pip
"$environment_dir/bin/python" -m pip install 'mlx-lm==0.31.3'

"$environment_dir/bin/python" - <<'PY'
import mlx.core as mx
import mlx_lm

print(f"mlx_default_device={mx.default_device()}")
print(f"mlx_lm_import={mlx_lm.__name__}")
a = mx.arange(1024, dtype=mx.float32)
b = mx.sum(a * a)
mx.eval(b)
print(f"mlx_compute_smoke={b.item():.0f}")
PY
