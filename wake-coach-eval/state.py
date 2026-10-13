"""Alarm state as the native app would supply it on each turn.

The clock advances one minute per turn and the reminder stage advances every
two turns, capped at the fact set's maximum stage.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

TIME_FMT = "%I:%M %p"


def parse_time(text: str) -> datetime:
    return datetime.strptime(text, TIME_FMT)


def format_time(t: datetime) -> str:
    return t.strftime(TIME_FMT).lstrip("0")


@dataclass(frozen=True)
class AlarmState:
    day: str
    now: str
    alarm_time: str
    minutes_since_alarm: int
    wake_reason: str | None
    deadline: str | None
    minutes_until_deadline: int | None
    stage: int
    max_stage: int

    @property
    def louder_allowed(self) -> bool:
        return self.stage < self.max_stage

    def render(self) -> str:
        reason = self.wake_reason or "none set"
        if self.deadline:
            deadline = f"{self.deadline} ({self.minutes_until_deadline} minutes from now)"
        else:
            deadline = "none known"
        return "\n".join([
            "ALARM STATE (from the app, always correct)",
            f"- Current time: {self.now}, {self.day}",
            f"- Alarm went off at: {self.alarm_time} ({self.minutes_since_alarm} minutes ago)",
            f"- Wake reason: {reason}",
            f"- Deadline: {deadline}",
            f"- Reminder stage: {self.stage} of {self.max_stage}",
            "- Walking detected: no",
            f"- Louder allowed: {'yes' if self.louder_allowed else 'no'}",
        ])


def state_for_turn(facts: dict, turn_index: int) -> AlarmState:
    now = parse_time(facts["start_time"]) + timedelta(minutes=turn_index)
    alarm = parse_time(facts["alarm_time"])
    deadline = facts.get("deadline")
    until = None
    if deadline:
        until = int((parse_time(deadline) - now).total_seconds() // 60)
    stage = min(facts["max_stage"], facts["start_stage"] + turn_index // 2)
    return AlarmState(
        day=facts["day"],
        now=format_time(now),
        alarm_time=facts["alarm_time"],
        minutes_since_alarm=int((now - alarm).total_seconds() // 60),
        wake_reason=facts.get("wake_reason"),
        deadline=deadline,
        minutes_until_deadline=until,
        stage=stage,
        max_stage=facts["max_stage"],
    )
