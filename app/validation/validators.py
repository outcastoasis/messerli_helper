from __future__ import annotations

from dataclasses import dataclass

from app.constants import (
    BLOCK_TYPE_BREAK,
    BLOCK_TYPE_COMPENSATION,
    BLOCK_TYPE_WORK,
    BREAK_REMARKS,
    COMPENSATION_REMARKS,
    WORK_REMARKS,
)
from app.models.time_block import TimeBlock
from app.utils.time_utils import is_quarter_hour


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    block_id: str | None = None


def sort_blocks(blocks: list[TimeBlock]) -> list[TimeBlock]:
    return sorted(blocks, key=lambda block: block.sort_key())


def validate_block(block: TimeBlock) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if block.block_type not in {
        BLOCK_TYPE_WORK,
        BLOCK_TYPE_BREAK,
        BLOCK_TYPE_COMPENSATION,
    }:
        issues.append(ValidationIssue("invalid_type", "Blocktyp ist ungültig.", block.id))
        return issues

    try:
        start_minutes = block.start_minutes
        end_minutes = block.end_minutes
    except ValueError as exc:
        issues.append(ValidationIssue("invalid_time", str(exc), block.id))
        return issues

    if start_minutes >= end_minutes:
        issues.append(
            ValidationIssue("time_order", "Startzeit muss vor Endzeit liegen.", block.id)
        )

    if not is_quarter_hour(start_minutes) or not is_quarter_hour(end_minutes):
        issues.append(
            ValidationIssue(
                "grid", "Zeiten müssen auf dem 15-Minuten-Raster liegen.", block.id
            )
        )

    if block.block_type == BLOCK_TYPE_WORK and not block.project_number.strip():
        issues.append(
            ValidationIssue(
                "project_required", "Projektnummer fehlt für Arbeitseintrag.", block.id
            )
        )

    if not block.remark.strip():
        issues.append(ValidationIssue("remark_required", "Bemerkung fehlt.", block.id))
    elif block.block_type == BLOCK_TYPE_WORK and block.remark not in WORK_REMARKS:
        issues.append(
            ValidationIssue(
                "remark_invalid",
                "Bemerkung ist für Arbeitseintrag nicht erlaubt.",
                block.id,
            )
        )
    elif block.block_type == BLOCK_TYPE_BREAK and block.remark not in BREAK_REMARKS:
        issues.append(
            ValidationIssue(
                "remark_invalid", "Bemerkung ist für Pause nicht erlaubt.", block.id
            )
        )
    elif (
        block.block_type == BLOCK_TYPE_COMPENSATION
        and block.remark not in COMPENSATION_REMARKS
    ):
        issues.append(
            ValidationIssue(
                "remark_invalid",
                "Bemerkung ist für Kompensation nicht erlaubt.",
                block.id,
            )
        )

    return issues


def validate_blocks(blocks: list[TimeBlock]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sorted_blocks = sort_blocks(blocks)

    for block in sorted_blocks:
        issues.extend(validate_block(block))

    for previous, current in zip(sorted_blocks, sorted_blocks[1:]):
        if previous.date != current.date:
            continue
        try:
            if current.start_minutes < previous.end_minutes:
                issues.append(
                    ValidationIssue(
                        "overlap",
                        f"Blöcke überlappen zwischen {previous.start_time} und {current.end_time}.",
                        current.id,
                    )
                )
        except ValueError:
            continue

    return issues
