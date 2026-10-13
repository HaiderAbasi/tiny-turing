"""Write manual labels compactly: default label plus per-turn exceptions.

  python label_tool.py coach minicpm5-1b x 'S04_no_reason:0=w:no reason set, acceptable but curt' ...

Codes: o = ok, w = weak, x = wrong. A note may follow the code after a colon.
"""

import json
import sys
from pathlib import Path

from summarize import load

CODES = {"o": "ok", "w": "weak", "x": "wrong"}


def main() -> None:
    arm, model, default, *overrides = sys.argv[1:]
    labels = {f"{r['scenario']}:{r['turn']}": [CODES[default], ""] for r in load(arm, model)}
    for item in overrides:
        key, value = item.split("=", 1)
        code, _, note = value.partition(":")
        if key not in labels:
            raise SystemExit(f"unknown turn {key}")
        labels[key] = [CODES[code], note]
    out = Path(__file__).parent / "labels" / arm / f"{model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(labels, indent=1) + "\n")
    print(f"{out}: {len(labels)} turns")


if __name__ == "__main__":
    main()
