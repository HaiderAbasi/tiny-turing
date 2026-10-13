#!/usr/bin/env bash
# Start llama-server for one model and wait until it is healthy.
# Usage: serve.sh <model.gguf> [port] [extra llama-server args...]
set -euo pipefail
model="$1"; port="${2:-8080}"; shift $(( $# > 1 ? 2 : 1 ))
"${LLAMA_SERVER:-llama-server}" -m "$model" --port "$port" -c 8192 -t "${THREADS:-4}" \
  --jinja --no-webui -np 1 "$@" > "${LOG:-/dev/null}" 2>&1 &
echo $! > "/tmp/llama-server-$port.pid"
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$port/health" >/dev/null && exit 0
  sleep 1
done
echo "server did not become healthy" >&2; exit 1
