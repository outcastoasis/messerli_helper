from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ProjectTemplate:
    id: str = field(default_factory=lambda: str(uuid4()))
    project_number: str = ""
    display_name: str = ""
    default_remark: str = ""
    is_favorite: bool = False

    def display_label(self) -> str:
        if self.display_name:
            return f"{self.project_number} - {self.display_name}"
        return self.project_number

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_number": self.project_number,
            "display_name": self.display_name,
            "default_remark": self.default_remark,
            "is_favorite": self.is_favorite,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectTemplate":
        return cls(
            id=str(payload.get("id") or uuid4()),
            project_number=str(payload.get("project_number", "")),
            display_name=str(payload.get("display_name", "")),
            default_remark=str(payload.get("default_remark", "")),
            is_favorite=bool(payload.get("is_favorite", False)),
        )
