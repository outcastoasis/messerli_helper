from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.constants import BLOCK_TYPE_BREAK, BLOCK_TYPE_COMPENSATION
from app.utils.time_utils import parse_time_text


@dataclass(slots=True)
class TimeBlock:
    id: str = field(default_factory=lambda: str(uuid4()))
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    block_type: str = "work"
    project_number: str = ""
    remark: str = ""
    custom_remark: str = ""

    @property
    def start_minutes(self) -> int:
        return parse_time_text(self.start_time)

    @property
    def end_minutes(self) -> int:
        return parse_time_text(self.end_time)

    @property
    def duration_minutes(self) -> int:
        return self.end_minutes - self.start_minutes

    @property
    def is_break(self) -> bool:
        return self.block_type == BLOCK_TYPE_BREAK

    @property
    def is_compensation(self) -> bool:
        return self.block_type == BLOCK_TYPE_COMPENSATION

    @property
    def is_productive(self) -> bool:
        return not self.is_break

    def display_project(self) -> str:
        if self.is_break:
            return "Pause"
        if self.is_compensation:
            return "Kompensation"
        return self.project_number

    def sort_key(self) -> tuple[str, int, int, str]:
        return (self.date, self.start_minutes, self.end_minutes, self.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "block_type": self.block_type,
            "project_number": self.project_number,
            "remark": self.remark,
            "custom_remark": self.custom_remark,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TimeBlock":
        return cls(
            id=str(payload.get("id") or uuid4()),
            date=str(payload.get("date", "")),
            start_time=str(payload.get("start_time", "")),
            end_time=str(payload.get("end_time", "")),
            block_type=str(payload.get("block_type", "work")),
            project_number=str(payload.get("project_number", "")),
            remark=str(payload.get("remark", "")),
            custom_remark=str(payload.get("custom_remark", "")),
        )
