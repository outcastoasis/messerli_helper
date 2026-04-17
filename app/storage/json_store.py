from __future__ import annotations

import json
from pathlib import Path

from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock


class JsonStorage:
    def __init__(self, root_dir: Path, seed_template_file: Path | None = None) -> None:
        self.root_dir = Path(root_dir)
        self.seed_template_file = Path(seed_template_file) if seed_template_file else None
        self.days_dir = self.root_dir / "days"
        self.templates_file = self.root_dir / "templates.json"
        self.preferences_file = self.root_dir / "preferences.json"
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.days_dir.mkdir(parents=True, exist_ok=True)

    def load_day(self, day: str) -> list[TimeBlock]:
        file_path = self.days_dir / f"{day}.json"
        if not file_path.exists():
            return []
        payload = self._read_json(file_path, default={"blocks": []})
        return [TimeBlock.from_dict(item) for item in payload.get("blocks", [])]

    def save_day(self, day: str, blocks: list[TimeBlock]) -> None:
        payload = {"date": day, "blocks": [block.to_dict() for block in blocks]}
        self._write_json(self.days_dir / f"{day}.json", payload)

    def load_templates(self) -> list[ProjectTemplate]:
        if not self.templates_file.exists() and self.seed_template_file and self.seed_template_file.exists():
            payload = self._read_json(self.seed_template_file, default=[])
            templates = [ProjectTemplate.from_dict(item) for item in payload]
            self.save_templates(templates)
            return templates
        payload = self._read_json(self.templates_file, default=[])
        return [ProjectTemplate.from_dict(item) for item in payload]

    def save_templates(self, templates: list[ProjectTemplate]) -> None:
        payload = [template.to_dict() for template in templates]
        self._write_json(self.templates_file, payload)

    def load_preferences(self) -> AppPreferences:
        payload = self._read_json(self.preferences_file, default={})
        return AppPreferences.from_dict(payload)

    def save_preferences(self, preferences: AppPreferences) -> None:
        self._write_json(self.preferences_file, preferences.to_dict())

    @staticmethod
    def _read_json(file_path: Path, default):
        if not file_path.exists():
            return default
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(file_path: Path, payload) -> None:
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

