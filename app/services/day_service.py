from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from app.constants import TARGET_PRODUCTIVE_MINUTES_BY_WEEKDAY
from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.storage.json_store import JsonStorage
from app.utils.time_utils import (
    format_messerli_time,
    minutes_to_time_text,
    parse_time_text,
)
from app.validation.validators import ValidationIssue, sort_blocks, validate_blocks


@dataclass(slots=True)
class ProductiveTimeSummary:
    productive_minutes: int
    target_minutes: int

    @property
    def difference_minutes(self) -> int:
        return self.productive_minutes - self.target_minutes


class DayService:
    def __init__(self, storage: JsonStorage) -> None:
        self.storage = storage

    def load_day(self, day: str) -> list[TimeBlock]:
        return sort_blocks(self.storage.load_day(day))

    def save_day(self, day: str, blocks: list[TimeBlock]) -> None:
        self.storage.save_day(day, sort_blocks(blocks))

    def load_templates(self) -> list[ProjectTemplate]:
        return self.storage.load_templates()

    def save_templates(self, templates: list[ProjectTemplate]) -> None:
        ordered = sorted(
            templates, key=lambda item: (item.project_number, item.display_name, item.id)
        )
        self.storage.save_templates(ordered)

    def load_preferences(self) -> AppPreferences:
        return self.storage.load_preferences()

    def save_preferences(self, preferences: AppPreferences) -> None:
        self.storage.save_preferences(preferences)

    def validate_day(self, blocks: list[TimeBlock]) -> list[ValidationIssue]:
        return validate_blocks(blocks)

    def sorted_blocks(self, blocks: list[TimeBlock]) -> list[TimeBlock]:
        return sort_blocks(blocks)

    def preview_rows(self, blocks: list[TimeBlock]) -> list[str]:
        rows: list[str] = []
        for block in self.sorted_blocks(blocks):
            rows.append(
                f"{block.display_project()} | {block.remark} | "
                f"{format_messerli_time(block.start_time)} | {format_messerli_time(block.end_time)}"
            )
        return rows

    def productive_minutes(self, blocks: list[TimeBlock]) -> int:
        return sum(block.duration_minutes for block in blocks if block.is_productive)

    def target_productive_minutes(self, day: str) -> int:
        weekday = date.fromisoformat(day).weekday()
        return TARGET_PRODUCTIVE_MINUTES_BY_WEEKDAY.get(weekday, 0)

    def productive_time_summary(
        self, day: str, blocks: list[TimeBlock]
    ) -> ProductiveTimeSummary:
        return ProductiveTimeSummary(
            productive_minutes=self.productive_minutes(blocks),
            target_minutes=self.target_productive_minutes(day),
        )

    def split_block(self, block: TimeBlock) -> tuple[TimeBlock, TimeBlock]:
        duration = block.duration_minutes
        if duration < 30:
            raise ValueError("Block ist zu kurz zum Teilen.")
        first_part = max(15, (duration // 30) * 15)
        middle = parse_time_text(block.start_time) + first_part
        first_block = replace(block, end_time=minutes_to_time_text(middle))
        second_block = replace(block, id="", start_time=minutes_to_time_text(middle))
        if not second_block.id:
            second_block = TimeBlock.from_dict(second_block.to_dict())
        return first_block, second_block
