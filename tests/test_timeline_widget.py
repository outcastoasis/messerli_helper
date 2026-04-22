from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.models.time_block import TimeBlock
from app.ui.timeline_widget import DayTimelineWidget


def test_clear_interaction_state_resets_drag_preview() -> None:
    app = QApplication.instance() or QApplication([])
    widget = DayTimelineWidget()
    widget._drag_mode = "move"
    widget._drag_block_id = "block-1"
    widget._drag_start_minutes = 300
    widget._drag_origin_minutes = 315
    widget._preview_start = 300
    widget._preview_end = 315

    widget._clear_interaction_state()

    assert app is not None
    assert widget._drag_mode is None
    assert widget._drag_block_id is None
    assert widget._drag_start_minutes is None
    assert widget._drag_origin_minutes is None
    assert widget._preview_start is None
    assert widget._preview_end is None


def test_delete_key_emits_delete_action_for_selected_block() -> None:
    app = QApplication.instance() or QApplication([])
    widget = DayTimelineWidget()
    widget.set_blocks(
        [
            TimeBlock(
                id="block-1",
                date="2026-04-22",
                start_time="08:00",
                end_time="08:15",
                project_number="25344",
                remark="Sys. AVOR",
            )
        ]
    )
    widget._set_selected_block("block-1")
    received: list[tuple[str, str]] = []
    widget.action_requested.connect(lambda action, block_id: received.append((action, block_id)))

    widget.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))

    assert app is not None
    assert received == [("delete", "block-1")]
    assert widget._selected_block_id is None
