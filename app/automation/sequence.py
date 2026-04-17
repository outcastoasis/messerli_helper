from __future__ import annotations

from dataclasses import dataclass

from app.constants import BLOCK_TYPE_BREAK, BLOCK_TYPE_COMPENSATION, WORK_COST_TYPES
from app.models.time_block import TimeBlock
from app.utils.time_utils import format_messerli_time
from app.validation.validators import sort_blocks


@dataclass(slots=True)
class AutomationStep:
    action: str
    value: str


def build_steps_for_block(block: TimeBlock) -> list[AutomationStep]:
    from_time = format_messerli_time(block.start_time)
    to_time = format_messerli_time(block.end_time)

    if block.block_type in {BLOCK_TYPE_BREAK, BLOCK_TYPE_COMPENSATION}:
        type_code = "P" if block.block_type == BLOCK_TYPE_BREAK else "K"
        return [
            AutomationStep("press", "enter"),
            AutomationStep("write", type_code),
            AutomationStep("press", "enter"),
            AutomationStep("write", block.remark),
            AutomationStep("press", "enter"),
            AutomationStep("write", from_time),
            AutomationStep("press", "enter"),
            AutomationStep("write", to_time),
            AutomationStep("press", "enter"),
            AutomationStep("press", "enter"),
        ]

    cost_type = WORK_COST_TYPES.get(block.remark)
    if cost_type is None:
        raise ValueError(f"Unbekannte Kostenart für Bemerkung: {block.remark}")

    return [
        AutomationStep("write", block.project_number),
        AutomationStep("press", "enter"),
        AutomationStep("write", cost_type),
        AutomationStep("press", "enter"),
        AutomationStep("write", block.remark),
        AutomationStep("press", "enter"),
        AutomationStep("write", from_time),
        AutomationStep("press", "enter"),
        AutomationStep("write", to_time),
        AutomationStep("press", "enter"),
    ]


def build_steps_for_blocks(blocks: list[TimeBlock]) -> list[AutomationStep]:
    steps: list[AutomationStep] = []
    for block in sort_blocks(blocks):
        steps.extend(build_steps_for_block(block))
    return steps
