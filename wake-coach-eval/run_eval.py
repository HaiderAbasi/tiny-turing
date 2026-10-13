"""Run the wake-coach scenarios against a llama-server endpoint or the baseline.

Usage:
  python run_eval.py --arm coach  --model qwen3-1.7b --url http://127.0.0.1:8080
  python run_eval.py --arm narrow --model qwen3-1.7b --url http://127.0.0.1:8080
  python run_eval.py --arm baseline

Each scenario is a fresh conversation. The sleeper's lines are fixed; the
model's own earlier replies are kept in the history.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

import checks
import native
import prompts
from models import MODELS
from state import state_for_turn

HERE = Path(__file__).parent


def chat(url: str, messages: list, schema: dict, sampling: dict, template_kwargs: dict) -> tuple[str, dict]:
    body = {
        "messages": messages,
        "max_tokens": 160,
        "seed": 7,
        "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}},
        **sampling,
    }
    if template_kwargs:
        body["chat_template_kwargs"] = template_kwargs
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    wall = time.monotonic() - start
    content = data["choices"][0]["message"].get("content") or ""
    timings = data.get("timings", {})
    return content, {
        "wall_s": round(wall, 2),
        "prompt_tokens": timings.get("prompt_n"),
        "prompt_tps": round(timings.get("prompt_per_second", 0), 1),
        "gen_tokens": timings.get("predicted_n"),
        "gen_tps": round(timings.get("predicted_per_second", 0), 1),
    }


def parse(content: str) -> dict | None:
    try:
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def run_scenario(scenario: dict, facts: dict, arm: str, url: str | None, cfg: dict | None) -> list[dict]:
    system = prompts.COACH_SYSTEM if arm == "coach" else prompts.NARROW_SYSTEM
    messages = [{"role": "system", "content": system}]
    session = checks.new_session()
    distress_latched = False
    records = []

    for i, turn in enumerate(scenario["turns"]):
        state = state_for_turn(facts, i)
        checks.update_session_before_turn(session, state, turn, facts)
        said = turn["said"]
        record = {"scenario": scenario["id"], "turn": i, "said": said, "tags": turn["tags"]}

        if arm == "baseline":
            out = native.baseline_turn(said, state, i, distress_latched)
            say, cue, intent, raw, perf = out["say"], out["cue"], out["intent"], None, {}
            distress_latched = out["distress"]
        else:
            if arm == "coach":
                user = prompts.coach_user_message(state, said)
                schema = prompts.COACH_SCHEMA
            else:
                user = prompts.narrow_user_message(said)
                schema = prompts.NARROW_SCHEMA
            messages.append({"role": "user", "content": user})
            raw, perf = chat(url, messages, schema, cfg["sampling"], cfg.get("template_kwargs", {}))
            messages.append({"role": "assistant", "content": raw})
            obj = parse(raw) or {}
            if arm == "coach":
                say, cue, intent = obj.get("say", ""), obj.get("cue"), None
            else:
                intent = obj.get("intent", "other")
                composed = native.compose(intent, obj.get("reply"), said, state, distress_latched)
                say, cue = composed["say"], composed["cue"]
                distress_latched = composed["distress"]
                record["model_reply"] = obj.get("reply")
                record["reply_rejected"] = composed["reply_rejected"]
            record["valid_json"] = bool(obj)

        result = checks.check_turn(say, cue, turn, state, session)
        session["previous_says"].append(say)
        record.update({
            "now": state.now, "stage": state.stage, "louder_allowed": state.louder_allowed,
            "raw": raw, "say": say, "cue": cue, "intent": intent,
            "intent_ok": None if intent is None else intent in turn["tags"],
            **result, "perf": perf,
        })
        records.append(record)
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["coach", "narrow", "baseline"], required=True)
    ap.add_argument("--model", default="baseline")
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--only", help="comma-separated scenario ids")
    args = ap.parse_args()

    spec = json.loads((HERE / "scenarios.json").read_text())
    cfg = None if args.arm == "baseline" else MODELS[args.model]
    wanted = set(args.only.split(",")) if args.only else None

    out_dir = HERE / "results" / args.arm
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.model}.jsonl"
    with out_path.open("w") as fh:
        for scenario in spec["scenarios"]:
            if wanted and scenario["id"] not in wanted:
                continue
            facts = spec["fact_sets"][scenario["facts"]]
            for rec in run_scenario(scenario, facts, args.arm, args.url, cfg):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                flag = " ".join(rec["critical"]) or "-"
                print(f"{rec['scenario']} t{rec['turn']} | {rec['said'][:40]!r} -> {rec['say'][:110]!r} [{rec['cue']}] {flag}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
