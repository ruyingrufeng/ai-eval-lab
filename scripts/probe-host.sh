#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
output_dir="$project_root/results/host"
output_file="$output_dir/$timestamp.txt"

mkdir -p "$output_dir"

{
  echo "timestamp_utc=$timestamp"
  echo "workspace=$project_root"
  echo "architecture=$(uname -m)"
  echo "kernel=$(uname -sr)"
  sw_vers 2>/dev/null || true
  echo
  system_profiler SPHardwareDataType SPDisplaysDataType 2>/dev/null || true
  echo
  df -h "$project_root"
  echo
  for command_name in git python3 node npm uv docker ollama ffmpeg; do
    command_path=$(command -v "$command_name" 2>/dev/null || true)
    if [ -n "$command_path" ]; then
      echo "$command_name=$command_path"
      "$command_name" --version 2>&1 | head -n 2 || true
    else
      echo "$command_name=NOT_FOUND"
    fi
  done
} > "$output_file"

printf '%s\n' "$output_file"
