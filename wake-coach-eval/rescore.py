"""Re-apply the current native.py and checks.py to stored results.

Narrow design: the model's intent and reply are stored per turn, so validator
or template changes are applied without re-running inference.
Coach design: the automatic checks are recomputed on the stored lines.

  python rescore.py
"""

import json
from pathlib import Path

import checks
import native
from state import state_for_turn

HERE = Path(__file__).parent


def rescore(path: Path, spec: dict) -> int:
    scenarios = {s["id"]: s for s in spec["scenarios"]}
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    changed = 0
    session, latched, current = None, False, None
    for rec in records:
        scenario = scenarios[rec["scenario"]]
        facts = spec["fact_sets"][scenario["facts"]]
        if rec["scenario"] != current:
            current, session, latched = rec["scenario"], checks.new_session(), False
        turn = scenario["turns"][rec["turn"]]
        state = state_for_turn(facts, rec["turn"])
        checks.update_session_before_turn(session, state, turn, facts)
        if rec.get("intent") is None:
            result = checks.check_turn(rec["say"], rec["cue"], turn, state, session)
            session["previous_says"].append(rec["say"])
            if result != {"critical": rec["critical"], "style": rec["style"]}:
                changed += 1
            rec.update(result)
            continue
        composed = native.compose(rec["intent"], rec.get("model_reply"), rec["said"], state, latched)
        latched = composed["distress"]
        result = checks.check_turn(composed["say"], composed["cue"], turn, state, session)
        session["previous_says"].append(composed["say"])
        if composed["say"] != rec["say"]:
            changed += 1
        rec.update({"say": composed["say"], "cue": composed["cue"],
                    "reply_rejected": composed["reply_rejected"], **result})
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return changed


def main() -> None:
    spec = json.loads((HERE / "scenarios.json").read_text())
    for arm in ("coach", "speech", "narrow"):
        for path in sorted((HERE / "results" / arm).glob("*.jsonl")):
            print(f"{arm}/{path.stem}: {rescore(path, spec)} turns changed")


if __name__ == "__main__":
    main()
