"""Guarded coach: the coach design with native safeguards applied afterwards.

For each coach turn:
- once distress has been reported in the session, the model's line is only
  kept if it passes the distress checks (no movement request, emergency advice
  where required); otherwise the native safe line is spoken;
- a model line that fails any automatic grounding or alarm-action check is
  replaced by the deterministic baseline line for that turn;
- the cue always comes from native policy, never from the model.

No inference is needed: this re-uses results/coach/*.jsonl and writes
results/guarded/*.jsonl. Manual labels are inherited from the coach labels
for turns whose spoken line did not change; changed turns are labeled
separately.

  python guard.py
"""

import json
from pathlib import Path

import checks
import native
from state import state_for_turn

HERE = Path(__file__).parent
GROUNDING = ("invented_time", "invented_duration", "wrong_day", "alarm_action", "empty")
DISTRESS = ("distress_movement", "no_emergency_advice")


def guard(records: list[dict], spec: dict) -> list[dict]:
    scenarios = {s["id"]: s for s in spec["scenarios"]}
    out, current, session, latched = [], None, None, False
    for rec in records:
        scenario = scenarios[rec["scenario"]]
        facts = spec["fact_sets"][scenario["facts"]]
        if rec["scenario"] != current:
            current, session, latched = rec["scenario"], checks.new_session(), False
        turn = scenario["turns"][rec["turn"]]
        state = state_for_turn(facts, rec["turn"])
        checks.update_session_before_turn(session, state, turn, facts)

        fallback = native.baseline_turn(rec["said"], state, rec["turn"], latched)
        latched = fallback["distress"]
        model_ok = rec["say"] and not any(c.startswith(GROUNDING) for c in rec["critical"])
        if latched:
            distress_ok = model_ok and not native.MOVEMENT_RE.search(rec["say"]) and not any(
                c.startswith(DISTRESS) for c in rec["critical"])
            if distress_ok:
                say, source = rec["say"], "model"
            else:
                say, source = native.SAFE_DISTRESS_LINE, "native_distress"
        elif model_ok:
            say, source = rec["say"], "model"
        else:
            say, source = fallback["say"], "native_fallback"
        cue = native.native_cue(fallback["intent"], latched, state)

        result = checks.check_turn(say, cue, turn, state, session)
        session["previous_says"].append(say)
        out.append({**rec, "say": say, "cue": cue, "source": source, **result})
    return out


def main() -> None:
    spec = json.loads((HERE / "scenarios.json").read_text())
    out_dir = HERE / "results" / "guarded"
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((HERE / "results" / "coach").glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        guarded = guard(records, spec)
        (out_dir / path.name).write_text("".join(json.dumps(r) + "\n" for r in guarded))

        coach_labels_path = HERE / "labels" / "coach" / f"{path.stem}.json"
        labels_path = HERE / "labels" / "guarded" / f"{path.stem}.json"
        if coach_labels_path.exists():
            coach_labels = json.loads(coach_labels_path.read_text())
            existing = json.loads(labels_path.read_text()) if labels_path.exists() else {}
            labels = {}
            for orig, new in zip(records, guarded):
                key = f"{new['scenario']}:{new['turn']}"
                if key in existing and existing[key][0] != "unreviewed":
                    labels[key] = existing[key]
                elif new["say"] == orig["say"]:
                    labels[key] = coach_labels.get(key, ["unreviewed", ""])
                elif key in existing and existing[key][0] != "unreviewed":
                    labels[key] = existing[key]
                else:
                    labels[key] = ["unreviewed", f"replaced by {new['source']}"]
            labels_path.parent.mkdir(parents=True, exist_ok=True)
            labels_path.write_text(json.dumps(labels, indent=1) + "\n")
        replaced = sum(1 for o, n in zip(records, guarded) if o["say"] != n["say"])
        print(f"{path.stem}: {replaced} of {len(guarded)} lines replaced")


if __name__ == "__main__":
    main()
