"""Native-side logic: distress detection, reply validation, line composition and
the deterministic (no-model) coach used as the baseline.

In the app this lives in Kotlin. It is reproduced here so the narrow prompt
design and the baseline can be scored with the same checks as the free coach.
"""

import re

DISTRESS_RE = re.compile(
    r"\b(dizz|faint|lightheaded|light-headed|sick|nause|vomit|throw(ing)? up|pain|hurts?|"
    r"chest|breath|breathe|spinning|unwell|ill\b|fell|fallen|bleed)",
    re.I,
)

NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|"
    "thirty|forty|fifty|sixty|half|quarter|hour|hours|minute|minutes"
)
UNSAFE_REPLY_RE = re.compile(
    rf"\d|\b({NUMBER_WORDS}|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"o'clock|am\b|pm\b|today|tomorrow|tonight|weekend|weekday|appointment|train|meeting|work|pause|skip|"
    r"snooz|cancel|turn(ed|ing)?( \w+){0,2} (off|down|up)|stopp?ed|is off|silenc|dismiss|louder|quieter|volume|"
    r"\bI('ll| will| can)\b)",
    re.I,
)
# A reaction must never talk the sleeper back to sleep or agree to delay.
SLEEP_RE = re.compile(
    r"\b(sleep|sweet dreams|rested|bed|more time|longer|wait|extra time|deserve a rest|rest now|take your time|slow down|no need to push|"
    r"enjoy (your|the|this)|have a (lovely|wonderful|nice|great) day)\b",
    re.I,
)
MOVEMENT_RE = re.compile(
    r"\b(get(ting)? up|stand(ing)?|walk(ing)?|out of bed|feet|mov(e|ing)|stretch(ing)?|steps?|kitchen|room|door|bathroom)\b", re.I
)

SAFE_DISTRESS_LINE = (
    "Stay where you are and take it slowly, sitting or lying down. "
    "If you have chest pain or trouble breathing, call emergency services."
)


def is_distress(said: str) -> bool:
    return bool(DISTRESS_RE.search(said or ""))


def validate_reply(reply: str, distress: bool) -> bool:
    reply = (reply or "").replace("\u2019", "'").replace("\u2018", "'")
    if not reply or len(reply.split()) > 20:
        return False
    if UNSAFE_REPLY_RE.search(reply):
        return False
    if distress and MOVEMENT_RE.search(reply):
        return False
    if not distress and (SLEEP_RE.search(reply) or re.search(r"\brest\b", reply, re.I)):
        return False
    return True


def template_line(intent: str, state) -> str:
    if intent == "ask_time":
        return f"It's {state.now} on {state.day}."
    if intent == "ask_reason":
        if state.wake_reason:
            return f"You set this alarm for: {state.wake_reason}."
        return "No reason was set for this alarm."
    if intent == "ask_time_left":
        if state.deadline:
            return f"{state.deadline} is {state.minutes_until_deadline} minutes away."
        return "I don't have a start time for anything today."
    if intent == "claim_awake":
        return "I'll stop once your phone notices you walking around."
    if intent == "request_alarm_off":
        return "I can't turn it off, but it stops once you're up and walking."
    if intent == "getting_up":
        return "Keep going and walk into another room."
    if intent == "silence":
        return "Are you awake? Try sitting up."
    if intent == "refuse_or_delay":
        return f"It's {state.now}. Try sitting up and putting your feet on the floor."
    return "Let's get you moving: sit up and put your feet on the floor."


def native_cue(intent: str, distress: bool, state) -> str:
    if distress:
        return "softer"
    if intent in ("silence", "refuse_or_delay") and state.louder_allowed:
        return "louder"
    return "same"


def compose(intent: str, reply: str | None, said: str, state, distress_latched: bool = False) -> dict:
    """Build the spoken line from a classified intent and an optional model reply.

    Once distress is reported, the session stays in distress mode: a later
    "should I get up?" must not be answered with a push to walk.
    """
    distress = distress_latched or is_distress(said) or intent == "distress"
    reply_ok = reply is not None and validate_reply(reply, distress)
    ack = reply.strip() if reply_ok else ""
    if distress:
        body = SAFE_DISTRESS_LINE
    else:
        body = template_line(intent, state)
    say = f"{ack} {body}".strip() if ack else body
    return {
        "say": say,
        "cue": native_cue(intent, distress, state),
        "reply_rejected": reply is not None and not reply_ok,
        "distress": distress,
    }


KEYWORD_INTENTS = [
    ("silence", re.compile(r"^\s*$")),
    ("distress", DISTRESS_RE),
    ("ask_time_left", re.compile(r"how (long|much time)|when does|until\b", re.I)),
    ("ask_time", re.compile(r"\btime\b|\btim\b|what day|weekend", re.I)),
    ("ask_reason", re.compile(r"\bwhy\b|what('s| is) (the alarm|this|it) for|somewhere to be|train\?", re.I)),
    ("request_alarm_off", re.compile(r"turn (it )?off|\bstop\b|cancel|shut up|alarm is off|leave me alone", re.I)),
    ("getting_up", re.compile(r"sitting|standing|walking|getting up|get up|feet|i'm up|kitchen", re.I)),
    ("claim_awake", re.compile(r"\bawake\b", re.I)),
    ("refuse_or_delay", re.compile(r"\bno\b|more minutes|snooze|tired|sleep|skip|minutes", re.I)),
]

BASELINE_ACKS = {
    "refuse_or_delay": ["I know, it's hard.", "I hear you.", "Not yet, sorry.", "Just a little effort now."],
    "claim_awake": ["Good to hear.", "Glad you're with me.", "Nice."],
    "request_alarm_off": ["I hear you.", "Sorry, not yet."],
    "getting_up": ["Nice work.", "That's it.", "Great."],
    "other": ["Okay.", "Mm-hm.", "I hear you."],
}


def baseline_intent(said: str) -> str:
    for intent, pattern in KEYWORD_INTENTS:
        if pattern.search(said or ""):
            return intent
    return "other"


def baseline_turn(said: str, state, turn_index: int, distress_latched: bool = False) -> dict:
    intent = baseline_intent(said)
    acks = BASELINE_ACKS.get(intent)
    ack = acks[turn_index % len(acks)] if acks else None
    out = compose(intent, ack, said, state, distress_latched)
    out["intent"] = intent
    return out
