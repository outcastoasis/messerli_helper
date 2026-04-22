from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QContextMenuEvent,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QMenu, QWidget

from app.constants import (
    PROJECT_BADGE_COLORS,
    REMARK_COLORS,
    SLOT_MINUTES,
    TIMELINE_END_HOUR,
    TIMELINE_PRIMARY_END_HOUR,
    TIMELINE_PRIMARY_START_HOUR,
    TIMELINE_START_HOUR,
)
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.utils.time_utils import minutes_to_time_text, snap_minutes
from app.validation.validators import sort_blocks


class DayTimelineWidget(QWidget):
    create_requested = Signal(str, str)
    edit_requested = Signal(str)
    move_or_resize_requested = Signal(str, str, str)
    action_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.blocks: list[TimeBlock] = []
        self._project_badge_assignments: dict[str, int] = {}
        self._template_names: dict[str, str] = {}
        self.left_gutter = 76
        self.top_padding = 16
        self.minimum_block_width = 240
        self.maximum_block_width = 280
        self.right_padding = 24
        self.slot_height = 30
        self.handle_size = 8
        self._block_rects: dict[str, QRect] = {}
        self._drag_mode: str | None = None
        self._drag_block_id: str | None = None
        self._drag_start_minutes: int | None = None
        self._drag_origin_minutes: int | None = None
        self._preview_start: int | None = None
        self._preview_end: int | None = None
        self.setMouseTracking(True)

    def set_blocks(self, blocks: list[TimeBlock]) -> None:
        self.blocks = sort_blocks(blocks)
        self.updateGeometry()
        self.update()

    def set_templates(self, templates: list[ProjectTemplate]) -> None:
        self._template_names = {
            template.project_number: template.display_name.strip()
            for template in templates
            if template.project_number
        }
        self.update()

    def set_project_badge_assignments(self, assignments: dict[str, int]) -> None:
        self._project_badge_assignments = dict(assignments)
        self.update()

    def sizeHint(self) -> QSize:
        total_slots = ((TIMELINE_END_HOUR - TIMELINE_START_HOUR) * 60) // SLOT_MINUTES
        height = self.top_padding * 2 + total_slots * self.slot_height
        width = self.left_gutter + self.maximum_block_width + self.right_padding
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor("#F8FAFD"))
        self._draw_grid(painter)
        self._draw_blocks(painter)
        self._draw_preview(painter)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        block = self._block_at(event.position().toPoint())
        if block is not None:
            self.edit_requested.emit(block.id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        point = event.position().toPoint()
        block = self._block_at(point)
        snapped_minutes = self._point_to_minutes(point)
        self._preview_start = None
        self._preview_end = None

        if block is None:
            start_minutes = self._point_to_minutes(point, rounding="floor")
            if start_minutes >= self._latest_supported_minutes():
                super().mousePressEvent(event)
                return
            self._drag_mode = "create"
            self._drag_start_minutes = start_minutes
            self._preview_start = start_minutes
            self._preview_end = start_minutes + SLOT_MINUTES
            self.update()
            return

        rect = self._block_rects[block.id]
        self._drag_block_id = block.id
        if abs(point.y() - rect.top()) <= self.handle_size:
            self._drag_mode = "resize_top"
        elif abs(point.y() - rect.bottom()) <= self.handle_size:
            self._drag_mode = "resize_bottom"
        else:
            self._drag_mode = "move"
            self._drag_origin_minutes = snapped_minutes
        self._preview_start = block.start_minutes
        self._preview_end = block.end_minutes
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = event.position().toPoint()
        if self._drag_mode is None:
            self._update_cursor(point)
            super().mouseMoveEvent(event)
            return

        current_minutes = self._point_to_minutes(point)
        if self._drag_mode == "create" and self._drag_start_minutes is not None:
            start = min(self._drag_start_minutes, current_minutes)
            end = max(self._drag_start_minutes, current_minutes)
            if start == end:
                end += SLOT_MINUTES
            self._preview_start = start
            self._preview_end = min(end, self._latest_supported_minutes())
        else:
            block = self._find_block(self._drag_block_id)
            if block is None:
                return
            if self._drag_mode == "move" and self._drag_origin_minutes is not None:
                delta = current_minutes - self._drag_origin_minutes
                duration = block.duration_minutes
                start = max(TIMELINE_START_HOUR * 60, block.start_minutes + delta)
                start = min(start, self._latest_supported_minutes() - duration)
                self._preview_start = start
                self._preview_end = start + duration
            elif self._drag_mode == "resize_top":
                new_start = min(current_minutes, block.end_minutes - SLOT_MINUTES)
                new_start = max(new_start, TIMELINE_START_HOUR * 60)
                self._preview_start = new_start
                self._preview_end = block.end_minutes
            elif self._drag_mode == "resize_bottom":
                new_end = max(current_minutes, block.start_minutes + SLOT_MINUTES)
                new_end = min(new_end, self._latest_supported_minutes())
                self._preview_start = block.start_minutes
                self._preview_end = new_end

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if (
            self._drag_mode == "create"
            and self._preview_start is not None
            and self._preview_end is not None
        ):
            if self._preview_end - self._preview_start >= SLOT_MINUTES:
                self.create_requested.emit(
                    minutes_to_time_text(self._preview_start),
                    minutes_to_time_text(self._preview_end),
                )
        elif (
            self._drag_block_id
            and self._preview_start is not None
            and self._preview_end is not None
        ):
            block = self._find_block(self._drag_block_id)
            if block is not None and (
                self._preview_start != block.start_minutes
                or self._preview_end != block.end_minutes
            ):
                self.move_or_resize_requested.emit(
                    block.id,
                    minutes_to_time_text(self._preview_start),
                    minutes_to_time_text(self._preview_end),
                )

        self._drag_mode = None
        self._drag_block_id = None
        self._drag_start_minutes = None
        self._drag_origin_minutes = None
        self._preview_start = None
        self._preview_end = None
        self.update()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        block = self._block_at(event.pos())
        if block is None:
            return
        menu = QMenu(self)
        edit_action = QAction("Bearbeiten", self)
        split_action = QAction("Teilen", self)
        delete_action = QAction("Löschen", self)

        edit_action.triggered.connect(lambda: self.edit_requested.emit(block.id))
        split_action.triggered.connect(
            lambda: self.action_requested.emit("split", block.id)
        )
        delete_action.triggered.connect(
            lambda: self.action_requested.emit("delete", block.id)
        )

        menu.addAction(edit_action)
        menu.addAction(split_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(event.globalPos())

    def _draw_grid(self, painter: QPainter) -> None:
        total_slots = ((TIMELINE_END_HOUR - TIMELINE_START_HOUR) * 60) // SLOT_MINUTES
        grid_width = self._grid_width()
        grid_rect = QRect(
            self.left_gutter,
            self.top_padding,
            grid_width,
            total_slots * self.slot_height,
        )

        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(
            grid_rect,
            12,
            12,
        )
        self._draw_dimmed_timeline_ranges(painter, grid_rect)

        for slot in range(total_slots + 1):
            y = self.top_padding + slot * self.slot_height
            is_hour = slot % 4 == 0
            painter.setPen(QPen(QColor("#C2CDDC" if is_hour else "#E2E8F0"), 1))
            painter.drawLine(self.left_gutter, y, self.left_gutter + grid_width, y)
            if is_hour:
                label_minutes = TIMELINE_START_HOUR * 60 + slot * SLOT_MINUTES
                label_color = "#334155"
                if not self._is_primary_timeline_minutes(label_minutes):
                    label_color = "#94A3B8"
                painter.setPen(QPen(QColor(label_color), 1))
                painter.drawText(12, y + 5, self._time_label_text(label_minutes))

    def _draw_blocks(self, painter: QPainter) -> None:
        self._block_rects = {}
        for block in self.blocks:
            rect = self._rect_for_block(block)
            self._block_rects[block.id] = rect
            color = QColor(REMARK_COLORS.get(block.remark, "#64748B"))
            painter.setPen(QPen(color.darker(140), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 8, 8)
            painter.setPen(QPen(self._text_color_for_background(color), 1))
            if block.is_break or block.is_compensation:
                self._draw_default_block_text(painter, rect, block)
            else:
                self._draw_work_block_text(painter, rect, block)

    def _draw_preview(self, painter: QPainter) -> None:
        if self._preview_start is None or self._preview_end is None:
            return
        rect = self._rect_for_range(self._preview_start, self._preview_end)
        painter.setPen(QPen(QColor("#1D4ED8"), 2, Qt.DashLine))
        painter.setBrush(QColor(59, 130, 246, 60))
        painter.drawRoundedRect(rect, 8, 8)

    def _point_to_minutes(self, point: QPoint, rounding: str = "nearest") -> int:
        relative_y = max(0, point.y() - self.top_padding)
        if rounding == "floor":
            slots = relative_y // self.slot_height
        else:
            slots = round(relative_y / self.slot_height)
        minutes = TIMELINE_START_HOUR * 60 + slots * SLOT_MINUTES
        minutes = snap_minutes(minutes)
        minutes = max(
            TIMELINE_START_HOUR * 60, min(minutes, self._latest_supported_minutes())
        )
        return minutes

    def y_position_for_minutes(self, total_minutes: int) -> int:
        clamped = max(TIMELINE_START_HOUR * 60, min(total_minutes, TIMELINE_END_HOUR * 60))
        slot = (clamped - TIMELINE_START_HOUR * 60) / SLOT_MINUTES
        return self.top_padding + round(slot * self.slot_height)

    def _rect_for_block(self, block: TimeBlock) -> QRect:
        return self._rect_for_range(block.start_minutes, block.end_minutes)

    def _rect_for_range(self, start_minutes: int, end_minutes: int) -> QRect:
        start_slot = (start_minutes - TIMELINE_START_HOUR * 60) / SLOT_MINUTES
        end_slot = (end_minutes - TIMELINE_START_HOUR * 60) / SLOT_MINUTES
        top = self.top_padding + round(start_slot * self.slot_height)
        height = max(
            self.slot_height, round((end_slot - start_slot) * self.slot_height)
        )
        return QRect(self.left_gutter + 4, top + 1, self._grid_width() - 8, height - 2)

    def _block_at(self, point: QPoint) -> TimeBlock | None:
        for block in reversed(self.blocks):
            rect = self._block_rects.get(block.id)
            if rect and rect.contains(point):
                return block
        return None

    def _find_block(self, block_id: str | None) -> TimeBlock | None:
        if not block_id:
            return None
        return next((block for block in self.blocks if block.id == block_id), None)

    def _latest_supported_minutes(self) -> int:
        return TIMELINE_END_HOUR * 60

    def _draw_dimmed_timeline_ranges(self, painter: QPainter, grid_rect: QRect) -> None:
        shaded_ranges = [
            (TIMELINE_START_HOUR * 60, TIMELINE_PRIMARY_START_HOUR * 60),
            (TIMELINE_PRIMARY_END_HOUR * 60, TIMELINE_END_HOUR * 60),
        ]
        painter.save()
        painter.setClipRect(grid_rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(148, 163, 184, 28))
        for start_minutes, end_minutes in shaded_ranges:
            if end_minutes <= start_minutes:
                continue
            top = self.y_position_for_minutes(start_minutes)
            bottom = self.y_position_for_minutes(end_minutes)
            painter.drawRect(
                grid_rect.left(),
                top,
                grid_rect.width(),
                max(0, bottom - top),
            )
        painter.restore()

    def _is_primary_timeline_minutes(self, total_minutes: int) -> bool:
        return TIMELINE_PRIMARY_START_HOUR * 60 <= total_minutes <= (
            TIMELINE_PRIMARY_END_HOUR * 60
        )

    def _time_label_text(self, total_minutes: int) -> str:
        if total_minutes == TIMELINE_END_HOUR * 60:
            return "24:00"
        return minutes_to_time_text(total_minutes)

    def _update_cursor(self, point: QPoint) -> None:
        block = self._block_at(point)
        if block is None:
            self.setCursor(Qt.CrossCursor)
            return
        rect = self._block_rects[block.id]
        if (
            abs(point.y() - rect.top()) <= self.handle_size
            or abs(point.y() - rect.bottom()) <= self.handle_size
        ):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.OpenHandCursor)

    @staticmethod
    def _text_color_for_background(color: QColor) -> QColor:
        brightness = (
            color.red() * 299 + color.green() * 587 + color.blue() * 114
        ) / 1000
        return QColor("#111111") if brightness > 160 else QColor("#FFFFFF")

    def _project_label_for_block(self, block: TimeBlock) -> str:
        if block.is_break or block.is_compensation:
            return block.display_project()
        return self._project_name_for_block(block) or block.project_number

    def _project_name_for_block(self, block: TimeBlock) -> str:
        return self._template_names.get(block.project_number, "").strip()

    def _draw_default_block_text(
        self, painter: QPainter, rect: QRect, block: TimeBlock
    ) -> None:
        text = (
            f"{self._project_label_for_block(block)}\n"
            f"{block.remark}\n"
            f"{block.start_time} - {block.end_time}"
        )
        painter.drawText(
            rect.adjusted(8, 6, -8, -6), Qt.AlignLeft | Qt.TextWordWrap, text
        )

    def _draw_work_block_text(
        self, painter: QPainter, rect: QRect, block: TimeBlock
    ) -> None:
        content_rect = rect.adjusted(8, 6, -8, -6)
        badge_rect = self._draw_project_badge(painter, content_rect, block.project_number)
        if badge_rect is not None:
            content_rect.setRight(max(content_rect.left(), badge_rect.left() - 8))

        project_line = self._project_name_for_block(block) or block.project_number
        lines = [
            project_line,
            block.remark,
            f"{block.start_time} - {block.end_time}",
        ]
        metrics = painter.fontMetrics()
        line_height = metrics.lineSpacing()
        y = content_rect.top()

        title_font = painter.font()
        title_font.setBold(True)
        painter.save()
        painter.setFont(title_font)
        title_metrics = painter.fontMetrics()
        title_rect = QRect(
            content_rect.left(),
            y,
            content_rect.width(),
            title_metrics.lineSpacing(),
        )
        painter.drawText(
            title_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            title_metrics.elidedText(project_line, Qt.ElideRight, content_rect.width()),
        )
        painter.restore()

        y += title_metrics.lineSpacing()
        for line in lines[1:]:
            line_rect = QRect(content_rect.left(), y, content_rect.width(), line_height)
            painter.drawText(
                line_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(line, Qt.ElideRight, content_rect.width()),
            )
            y += line_height

    def _draw_project_badge(
        self, painter: QPainter, content_rect: QRect, project_number: str
    ) -> QRect | None:
        if not project_number:
            return None

        painter.save()
        badge_font = painter.font()
        badge_font.setBold(True)
        painter.setFont(badge_font)
        metrics = painter.fontMetrics()
        badge_text = metrics.elidedText(project_number, Qt.ElideRight, 96)
        badge_height = metrics.height() + 6
        badge_width = metrics.horizontalAdvance(badge_text) + 14
        badge_rect = QRect(
            content_rect.right() - badge_width,
            content_rect.top(),
            badge_width,
            badge_height,
        )
        badge_color = self._project_badge_color(project_number)
        painter.setPen(QPen(badge_color.darker(125), 1))
        painter.setBrush(badge_color)
        corner_radius = badge_rect.height() / 2
        painter.drawRoundedRect(badge_rect, corner_radius, corner_radius)
        painter.setPen(QPen(self._text_color_for_background(badge_color), 1))
        painter.drawText(badge_rect, Qt.AlignCenter, badge_text)
        painter.restore()
        return badge_rect

    def _project_badge_color(self, project_number: str) -> QColor:
        color_index = self._project_badge_assignments.get(project_number)
        if color_index is None or not 0 <= color_index < len(PROJECT_BADGE_COLORS):
            return QColor("#E2E8F0")
        return QColor(PROJECT_BADGE_COLORS[color_index])

    def _grid_width(self) -> int:
        available_width = self.width() - self.left_gutter - self.right_padding
        return min(
            self.maximum_block_width,
            max(self.minimum_block_width, available_width),
        )
