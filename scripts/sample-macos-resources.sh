#!/bin/sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 OUTPUT.jsonl INTERVAL_SECONDS [PID]" >&2
  exit 2
fi

output_file=$1
interval_seconds=$2
target_pid=${3:-}

mkdir -p "$(dirname "$output_file")"

while :; do
  recorded_at=$(date '+%Y-%m-%dT%H:%M:%S%z')
  epoch_seconds=$(date '+%s')
  memory_free_percent=$(memory_pressure -Q 2>/dev/null | awk -F': ' '/free percentage/ {gsub(/%/,"",$2); print $2}')
  swap_line=$(sysctl -n vm.swapusage 2>/dev/null || true)
  swap_used_mib=$(printf '%s\n' "$swap_line" | awk '{for(i=1;i<=NF;i++) if($i=="used") {gsub(/M/,"",$(i+2)); print $(i+2)}}')
  vm_json=$(vm_stat | awk '
    NR==1 {gsub(/[^0-9]/,"",$8); page=$8; next}
    /Pages free:/ {gsub(/\./,"",$3); free=$3}
    /Pages active:/ {gsub(/\./,"",$3); active=$3}
    /Pages inactive:/ {gsub(/\./,"",$3); inactive=$3}
    /Pages wired down:/ {gsub(/\./,"",$4); wired=$4}
    /Pages occupied by compressor:/ {gsub(/\./,"",$5); compressor=$5}
    /Pageouts:/ {gsub(/\./,"",$2); pageouts=$2}
    END {printf "{\"page_size\":%s,\"free_pages\":%s,\"active_pages\":%s,\"inactive_pages\":%s,\"wired_pages\":%s,\"compressor_pages\":%s,\"pageouts\":%s}",page,free,active,inactive,wired,compressor,pageouts}')
  load_avg=$(sysctl -n vm.loadavg | tr -d '{}')
  pid_json=null
  if [ -n "$target_pid" ] && kill -0 "$target_pid" 2>/dev/null; then
    pid_values=$(ps -o rss=,%cpu=,etime= -p "$target_pid" | awk '{$1=$1; print}')
    pid_rss_kib=$(printf '%s\n' "$pid_values" | awk '{print $1}')
    pid_cpu_percent=$(printf '%s\n' "$pid_values" | awk '{print $2}')
    pid_elapsed=$(printf '%s\n' "$pid_values" | awk '{print $3}')
    pid_json="{\"pid\":$target_pid,\"rss_kib\":$pid_rss_kib,\"cpu_percent\":$pid_cpu_percent,\"elapsed\":\"$pid_elapsed\"}"
  fi
  printf '{"recorded_at":"%s","epoch_seconds":%s,"memory_free_percent":%s,"swap_used_mib":%s,"load_avg":"%s","vm":%s,"process":%s}\n' \
    "$recorded_at" "$epoch_seconds" "${memory_free_percent:-null}" "${swap_used_mib:-null}" "$load_avg" "$vm_json" "$pid_json" >> "$output_file"
  sleep "$interval_seconds"
done
