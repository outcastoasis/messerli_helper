from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.validation.validators import (
    has_duplicate_project_number,
    sort_blocks,
    validate_blocks,
)


def make_block(**overrides) -> TimeBlock:
    payload = {
        "date": "2026-04-15",
        "start_time": "08:00",
        "end_time": "09:00",
        "block_type": "work",
        "project_number": "25344",
        "remark": "Sys. Installation",
    }
    payload.update(overrides)
    return TimeBlock(**payload)


def test_overlap_is_detected() -> None:
    issues = validate_blocks(
        [
            make_block(start_time="08:00", end_time="09:00"),
            make_block(start_time="08:45", end_time="10:00"),
        ]
    )
    assert any(issue.code == "overlap" for issue in issues)


def test_empty_project_for_work_is_detected() -> None:
    issues = validate_blocks([make_block(project_number="")])
    assert any(issue.code == "project_required" for issue in issues)


def test_break_without_project_is_accepted() -> None:
    issues = validate_blocks(
        [make_block(block_type="break", project_number="", remark="Mittag", start_time="12:00", end_time="13:00")]
    )
    assert issues == []


def test_compensation_without_project_is_accepted() -> None:
    issues = validate_blocks(
        [
            make_block(
                block_type="compensation",
                project_number="",
                remark="Kompensation",
                start_time="12:00",
                end_time="13:00",
            )
        ]
    )
    assert issues == []


def test_invalid_remark_is_detected() -> None:
    issues = validate_blocks([make_block(remark="Mittag")])
    assert any(issue.code == "remark_invalid" for issue in issues)


def test_general_remark_requires_custom_text() -> None:
    issues = validate_blocks([make_block(remark="10: Allgemein", custom_remark="")])
    assert any(issue.code == "custom_remark_required" for issue in issues)


def test_general_remark_with_custom_text_is_accepted() -> None:
    issues = validate_blocks(
        [make_block(remark="10: Allgemein", custom_remark="Individuelle Abklaerung")]
    )
    assert issues == []


def test_start_must_be_before_end() -> None:
    issues = validate_blocks([make_block(start_time="10:00", end_time="10:00")])
    assert any(issue.code == "time_order" for issue in issues)


def test_sorted_blocks_are_accepted() -> None:
    blocks = [
        make_block(start_time="10:00", end_time="10:30", remark="Admin"),
        make_block(start_time="08:00", end_time="09:00"),
        make_block(start_time="09:00", end_time="09:30", remark="Sys. AVOR"),
    ]
    issues = validate_blocks(sort_blocks(blocks))
    assert issues == []


def test_break_with_work_remark_is_detected() -> None:
    issues = validate_blocks(
        [make_block(block_type="break", project_number="", remark="Sys. Installation", start_time="12:00", end_time="12:30")]
    )
    assert any(issue.code == "remark_invalid" for issue in issues)


def test_work_entry_with_break_remark_is_detected() -> None:
    issues = validate_blocks([make_block(remark="Pause")])
    assert any(issue.code == "remark_invalid" for issue in issues)


def test_compensation_with_wrong_remark_is_detected() -> None:
    issues = validate_blocks(
        [
            make_block(
                block_type="compensation",
                project_number="",
                remark="Pause",
                start_time="12:00",
                end_time="12:30",
            )
        ]
    )
    assert any(issue.code == "remark_invalid" for issue in issues)


def test_sorting_is_chronological() -> None:
    sorted_blocks = sort_blocks(
        [
            make_block(start_time="11:00", end_time="11:30"),
            make_block(start_time="07:00", end_time="08:00"),
            make_block(start_time="09:15", end_time="10:00"),
        ]
    )
    assert [block.start_time for block in sorted_blocks] == ["07:00", "09:15", "11:00"]


def test_duplicate_project_number_is_detected_for_templates() -> None:
    templates = [
        ProjectTemplate(id="a", project_number="25344", display_name="Muster"),
        ProjectTemplate(id="b", project_number="27050", display_name="Admin"),
    ]

    assert has_duplicate_project_number(templates, "25344")
    assert not has_duplicate_project_number(templates, "25344", exclude_id="a")
    assert not has_duplicate_project_number(templates, "99999")
