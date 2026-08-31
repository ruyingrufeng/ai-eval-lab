#!/bin/zsh
set -euo pipefail

repo_dir="${0:A:h:h}"
dsh_home_dir="${DSH_HOME:-$HOME/.dsh}"
settings_file="$dsh_home_dir/settings.yaml"
patch_file="$repo_dir/benchmarks/dsh/glm47-validated-headless.patch.yml"

if [[ ! -f "$settings_file" ]]; then
  print -u2 "dsh settings not found: $settings_file"
  exit 2
fi

route=$(awk '
  /^agent-default-model:/ { active=1; next }
  active && /^[^[:space:]]/ { active=0 }
  active && $1 == "provider:" { provider=$2 }
  active && $1 == "model:" { model=$2 }
  END { print provider "/" model }
' "$settings_file")

if [[ "$route" != "glm4.7-flash-local/glm4.7-flash" ]]; then
  print -u2 "refusing to run: dsh runtime route is $route, expected glm4.7-flash-local/glm4.7-flash"
  print -u2 "select the GLM route explicitly, then rerun this wrapper"
  exit 2
fi

exec dsh --profile headless --patch "$patch_file" "$@"
