from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.constants import DEFAULT_COUNTDOWN_SECONDS, DEFAULT_TYPING_INTERVAL


@dataclass(slots=True)
class AppPreferences:
    last_project_number: str = ""
    last_work_remark: str = ""
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS
    typing_interval: float = DEFAULT_TYPING_INTERVAL
    project_badge_assignments: dict[str, int] = field(default_factory=dict)
    skipped_update_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_project_number": self.last_project_number,
            "last_work_remark": self.last_work_remark,
            "countdown_seconds": self.countdown_seconds,
            "typing_interval": self.typing_interval,
            "project_badge_assignments": self.project_badge_assignments,
            "skipped_update_version": self.skipped_update_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppPreferences":
        raw_assignments = payload.get("project_badge_assignments", {})
        assignments: dict[str, int] = {}
        if isinstance(raw_assignments, dict):
            for project_number, color_index in raw_assignments.items():
                try:
                    assignments[str(project_number)] = int(color_index)
                except (TypeError, ValueError):
                    continue
        return cls(
            last_project_number=str(payload.get("last_project_number", "")),
            last_work_remark=str(payload.get("last_work_remark", "")),
            countdown_seconds=int(
                payload.get("countdown_seconds", DEFAULT_COUNTDOWN_SECONDS)
            ),
            typing_interval=float(payload.get("typing_interval", DEFAULT_TYPING_INTERVAL)),
            project_badge_assignments=assignments,
            skipped_update_version=str(payload.get("skipped_update_version", "")),
        )
