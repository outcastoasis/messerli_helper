from __future__ import annotations

from dataclasses import dataclass

from app.constants import (
    BLOCK_TYPE_BREAK,
    BLOCK_TYPE_COMPENSATION,
    GENERAL_WORK_REMARK,
    WORK_COST_TYPES,
)
from app.models.time_block import TimeBlock
from app.utils.time_utils import format_messerli_time
from app.validation.validators import sort_blocks


@dataclass(slots=True)
class AutomationStep:
    action: str
    value: str


def build_lunch_expense_steps() -> list[AutomationStep]:
    return [
        AutomationStep("press", "tab"),
        AutomationStep("write", "52"),
        AutomationStep("press", "enter"),
        AutomationStep("write", "Mittag"),
        AutomationStep("press", "enter"),
        AutomationStep("wait", "0.35"),
        AutomationStep("press", "enter"),
        AutomationStep("write", "1"),
        AutomationStep("press", "enter"),
        AutomationStep("press", "tab"),
    ]


def build_steps_for_block(
    block: TimeBlock, include_lunch_expense: bool = False
) -> list[AutomationStep]:
    from_time = format_messerli_time(block.start_time)
    to_time = format_messerli_time(block.end_time)

    if block.block_type in {BLOCK_TYPE_BREAK, BLOCK_TYPE_COMPENSATION}:
        type_code = "P" if block.block_type == BLOCK_TYPE_BREAK else "K"
        steps = [
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
        if include_lunch_expense:
            steps.extend(build_lunch_expense_steps())
        return steps

    cost_type = WORK_COST_TYPES.get(block.remark)
    if cost_type is None:
        raise ValueError(f"Unbekannte Kostenart für Bemerkung: {block.remark}")

    remark_text = (
        block.custom_remark.strip()
        if block.remark == GENERAL_WORK_REMARK
        else block.remark
    )
    if block.remark == GENERAL_WORK_REMARK and not remark_text:
        raise ValueError("Allgemeine Bemerkung darf nicht leer sein.")

    return [
        AutomationStep("write", block.project_number),
        AutomationStep("press", "enter"),
        AutomationStep("write", cost_type),
        AutomationStep("press", "enter"),
        AutomationStep("write", remark_text),
        AutomationStep("press", "enter"),
        AutomationStep("write", from_time),
        AutomationStep("press", "enter"),
        AutomationStep("write", to_time),
        AutomationStep("press", "enter"),
    ]


def build_steps_for_blocks(
    blocks: list[TimeBlock], include_lunch_expenses: bool = False
) -> list[AutomationStep]:
    steps: list[AutomationStep] = []
    lunch_expense_added = False
    for block in sort_blocks(blocks):
        add_lunch_expense = (
            include_lunch_expenses
            and not lunch_expense_added
            and block.block_type == BLOCK_TYPE_BREAK
            and block.remark == "Mittag"
        )
        steps.extend(build_steps_for_block(block, add_lunch_expense))
        lunch_expense_added = lunch_expense_added or add_lunch_expense
    return steps
