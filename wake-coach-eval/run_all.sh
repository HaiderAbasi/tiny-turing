#!/usr/bin/env bash
# Run both prompt designs for every model in models.py, one server at a time.
# Usage: MODEL_DIR=/path/to/gguf ./run_all.sh [model ...]
set -uo pipefail
cd "$(dirname "$0")"
models=("$@")
if [ ${#models[@]} -eq 0 ]; then
  mapfile -t models < <(python3 -c "from models import MODELS; print('\n'.join(MODELS))")
fi
python3 run_eval.py --arm baseline > /dev/null
for m in "${models[@]}"; do
  file=$(python3 -c "from models import MODELS; print(MODELS['$m']['file'])")
  echo "== $m"
  ./serve.sh "$MODEL_DIR/$file" || continue
  for arm in coach narrow; do
    python3 run_eval.py --arm "$arm" --model "$m" > "results/$arm/$m.log" 2>&1
    echo "   $arm: $(grep -c . "results/$arm/$m.jsonl") turns"
  done
  kill "$(cat /tmp/llama-server-8080.pid)"; sleep 2
done
