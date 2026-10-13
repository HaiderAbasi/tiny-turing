"""Peak resident memory of llama-server per model after a short conversation.

Starts each model's server (mmap on, as on Android), runs one four-turn
scenario, and reads VmHWM from /proc. Numbers are for llama.cpp on x86 Linux;
they indicate relative footprint, not exact Android figures.

  LLAMA_SERVER=... MODEL_DIR=... python measure_memory.py
"""

import json
import os
import subprocess
import time
from pathlib import Path

from models import MODELS

HERE = Path(__file__).parent


def peak_rss_mb(pid: int) -> float:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) / 1024
    return float("nan")


def main() -> None:
    model_dir = Path(os.environ["MODEL_DIR"])
    results = {}
    for name, cfg in MODELS.items():
        path = model_dir / cfg["file"]
        subprocess.run([str(HERE / "serve.sh"), str(path), "8090", *cfg.get("server_args", [])], check=True)
        pid = int(Path("/tmp/llama-server-8090.pid").read_text())
        subprocess.run(["python3", str(HERE / "run_eval.py"), "--arm", "coach", "--model", name,
                        "--url", "http://127.0.0.1:8090", "--only", "S01_resist", "--seed", "99"],
                       check=True, capture_output=True)
        results[name] = {"file_gb": round(path.stat().st_size / 1e9, 2), "peak_rss_mb": round(peak_rss_mb(pid))}
        subprocess.run(["kill", str(pid)])
        time.sleep(2)
        (HERE / "results" / "coach" / f"{name}-seed99.jsonl").unlink(missing_ok=True)
        print(name, results[name], flush=True)
    (HERE / "results" / "memory.json").write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
