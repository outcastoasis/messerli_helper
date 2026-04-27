from app.automation.sequence import build_steps_for_block, build_steps_for_blocks
from app.models.time_block import TimeBlock


def test_sequence_for_normal_entry() -> None:
    block = TimeBlock(
        date="2026-04-15",
        start_time="06:30",
        end_time="10:00",
        block_type="work",
        project_number="25344",
        remark="Sys. Installation",
    )

    steps = build_steps_for_block(block)

    assert [(step.action, step.value) for step in steps] == [
        ("write", "25344"),
        ("press", "enter"),
        ("write", "30.09"),
        ("press", "enter"),
        ("write", "Sys. Installation"),
        ("press", "enter"),
        ("write", "06.50"),
        ("press", "enter"),
        ("write", "10.00"),
        ("press", "enter"),
    ]


def test_sequence_for_general_entry_writes_custom_remark() -> None:
    block = TimeBlock(
        date="2026-04-15",
        start_time="06:30",
        end_time="10:00",
        block_type="work",
        project_number="25344",
        remark="10: Allgemein",
        custom_remark="Individuelle Abklaerung",
    )

    steps = build_steps_for_block(block)

    assert [(step.action, step.value) for step in steps][0:6] == [
        ("write", "25344"),
        ("press", "enter"),
        ("write", "10"),
        ("press", "enter"),
        ("write", "Individuelle Abklaerung"),
        ("press", "enter"),
    ]


def test_sequence_for_break_entry() -> None:
    block = TimeBlock(
        date="2026-04-15",
        start_time="12:00",
        end_time="13:00",
        block_type="break",
        project_number="",
        remark="Mittag",
    )

    steps = build_steps_for_block(block)

    assert [(step.action, step.value) for step in steps] == [
        ("press", "enter"),
        ("write", "P"),
        ("press", "enter"),
        ("write", "Mittag"),
        ("press", "enter"),
        ("write", "12.00"),
        ("press", "enter"),
        ("write", "13.00"),
        ("press", "enter"),
        ("press", "enter"),
    ]


def test_sequence_for_compensation_entry() -> None:
    block = TimeBlock(
        date="2026-04-15",
        start_time="16:00",
        end_time="17:00",
        block_type="compensation",
        project_number="",
        remark="Kompensation",
    )

    steps = build_steps_for_block(block)

    assert [(step.action, step.value) for step in steps] == [
        ("press", "enter"),
        ("write", "K"),
        ("press", "enter"),
        ("write", "Kompensation"),
        ("press", "enter"),
        ("write", "16.00"),
        ("press", "enter"),
        ("write", "17.00"),
        ("press", "enter"),
        ("press", "enter"),
    ]


def test_sequence_supports_day_end_time() -> None:
    block = TimeBlock(
        date="2026-04-15",
        start_time="23:00",
        end_time="24:00",
        block_type="work",
        project_number="25344",
        remark="Sys. Installation",
    )

    steps = build_steps_for_block(block)

    assert [(step.action, step.value) for step in steps][-2:] == [
        ("write", "24.00"),
        ("press", "enter"),
    ]


def test_sequence_for_multiple_blocks_is_sorted() -> None:
    steps = build_steps_for_blocks(
        [
            TimeBlock(
                date="2026-04-15",
                start_time="10:00",
                end_time="10:30",
                block_type="work",
                project_number="27050",
                remark="Admin",
            ),
            TimeBlock(
                date="2026-04-15",
                start_time="06:30",
                end_time="10:00",
                block_type="work",
                project_number="25344",
                remark="Sys. Installation",
            ),
        ]
    )

    assert (steps[0].action, steps[0].value) == ("write", "25344")


def test_sequence_after_break_starts_with_project_then_cost_type() -> None:
    steps = build_steps_for_blocks(
        [
            TimeBlock(
                date="2026-04-15",
                start_time="12:00",
                end_time="13:00",
                block_type="break",
                project_number="",
                remark="Mittag",
            ),
            TimeBlock(
                date="2026-04-15",
                start_time="13:00",
                end_time="15:00",
                block_type="work",
                project_number="25344",
                remark="Sys. Installation",
            ),
        ]
    )

    assert [(step.action, step.value) for step in steps[8:13]] == [
        ("press", "enter"),
        ("press", "enter"),
        ("write", "25344"),
        ("press", "enter"),
        ("write", "30.09"),
    ]
