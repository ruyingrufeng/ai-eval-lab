#!/bin/bash
# Dispatch to the existing isolated installation; no model copies in this repo.
set -euo pipefail
fish_project="${FISH_S2_PROJECT:-/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local}"
if [ ! -x "$fish_project/run.sh" ]; then
  echo "找不到 Fish S2 部署目录，请设置 FISH_S2_PROJECT。" >&2
  exit 1
fi
exec "$fish_project/run.sh" "$@"
