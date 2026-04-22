from __future__ import annotations

import re

from app.constants import MESSERLI_MINUTE_SUFFIX, SLOT_MINUTES

TIME_PATTERN = re.compile(r"^(?P<hour>\d{2}):(?P<minute>\d{2})$")


def parse_time_text(value: str) -> int:
    match = TIME_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"Invalid time format: {value!r}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour == 24 and minute == 0:
        return 24 * 60
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time value: {value!r}")
    return hour * 60 + minute


def minutes_to_time_text(total_minutes: int) -> str:
    if total_minutes < 0 or total_minutes > 24 * 60:
        raise ValueError(f"Minutes out of range: {total_minutes}")
    if total_minutes == 24 * 60:
        return "24:00"
    hour, minute = divmod(total_minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def is_quarter_hour(total_minutes: int) -> bool:
    return total_minutes % SLOT_MINUTES == 0


def snap_minutes(total_minutes: int, step: int = SLOT_MINUTES) -> int:
    remainder = total_minutes % step
    if remainder == 0:
        return total_minutes
    down = total_minutes - remainder
    up = down + step
    if total_minutes - down < up - total_minutes:
        return down
    return up


def format_messerli_time(time_text: str) -> str:
    total_minutes = parse_time_text(time_text)
    if total_minutes == 24 * 60:
        return "24.00"
    hour, minute = divmod(total_minutes, 60)
    if minute not in MESSERLI_MINUTE_SUFFIX:
        raise ValueError(f"Time is not on a 15-minute grid: {time_text!r}")
    return f"{hour:02d}.{MESSERLI_MINUTE_SUFFIX[minute]}"


def format_duration_minutes(total_minutes: int, include_sign: bool = False) -> str:
    sign = ""
    minutes = total_minutes
    if minutes < 0:
        sign = "-"
        minutes = abs(minutes)
    elif include_sign and minutes > 0:
        sign = "+"

    hours, remainder = divmod(minutes, 60)
    return f"{sign}{hours}:{remainder:02d}"
