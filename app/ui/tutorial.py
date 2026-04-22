from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.ui.block_editor import BlockEditorDialog


@dataclass(slots=True)
class TutorialStep:
    title: str
    description: str
    host_resolver: Callable[[], QWidget | None]
    target_resolver: Callable[[], QWidget | None]
    on_enter: Callable[["TutorialController"], None] | None = None
    on_exit: Callable[["TutorialController"], None] | None = None


class TutorialOverlay(QWidget):
    next_requested = Signal()
    previous_requested = Signal()
    close_requested = Signal()

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self._target: QWidget | None = None
        self._title = ""
        self._description = ""
        self._step_label = ""

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self.setFocusPolicy(Qt.StrongFocus)

        self.panel = QFrame(self)
        self.panel.setObjectName("TutorialPanel")
        self.panel.setStyleSheet(
            """
            QFrame#TutorialPanel {
                background: #FFFDF8;
                border: 1px solid #D7DFEC;
                border-radius: 18px;
            }
            QLabel#TutorialStep {
                color: #1D4ED8;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#TutorialTitle {
                color: #0F172A;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#TutorialBody {
                color: #334155;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton#TutorialPrimaryButton,
            QPushButton#TutorialSecondaryButton,
            QPushButton#TutorialGhostButton {
                min-height: 34px;
                border-radius: 10px;
                padding: 0 14px;
                font-weight: 600;
            }
            QPushButton#TutorialPrimaryButton {
                background: #2563EB;
                color: #FFFFFF;
                border: 1px solid #2563EB;
            }
            QPushButton#TutorialPrimaryButton:hover {
                background: #1D4ED8;
                border-color: #1D4ED8;
            }
            QPushButton#TutorialSecondaryButton {
                background: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
            }
            QPushButton#TutorialGhostButton {
                background: transparent;
                color: #475569;
                border: 1px solid transparent;
            }
            """
        )

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 18, 18, 16)
        panel_layout.setSpacing(10)

        self.step_label = QLabel()
        self.step_label.setObjectName("TutorialStep")
        panel_layout.addWidget(self.step_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("TutorialTitle")
        self.title_label.setWordWrap(True)
        panel_layout.addWidget(self.title_label)

        self.body_label = QLabel()
        self.body_label.setObjectName("TutorialBody")
        self.body_label.setWordWrap(True)
        panel_layout.addWidget(self.body_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(8)

        self.close_button = QPushButton("Beenden")
        self.close_button.setObjectName("TutorialGhostButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        button_row.addWidget(self.close_button)

        button_row.addStretch()

        self.previous_button = QPushButton("Zurück")
        self.previous_button.setObjectName("TutorialSecondaryButton")
        self.previous_button.clicked.connect(self.previous_requested.emit)
        button_row.addWidget(self.previous_button)

        self.next_button = QPushButton("Weiter")
        self.next_button.setObjectName("TutorialPrimaryButton")
        self.next_button.clicked.connect(self.next_requested.emit)
        button_row.addWidget(self.next_button)
        panel_layout.addLayout(button_row)

        self._host.installEventFilter(self)
        self._sync_geometry()
        self.hide()

    def closeEvent(self, event) -> None:
        self._host.removeEventFilter(self)
        super().closeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._host and event.type() in {
            QEvent.Resize,
            QEvent.Move,
            QEvent.Show,
        }:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def set_step(
        self,
        title: str,
        description: str,
        step_label: str,
        is_first: bool,
        is_last: bool,
    ) -> None:
        self._title = title
        self._description = description
        self._step_label = step_label
        self.step_label.setText(step_label)
        self.title_label.setText(title)
        self.body_label.setText(description)
        self.previous_button.setVisible(not is_first)
        self.next_button.setText("Fertig" if is_last else "Weiter")
        self._reposition_panel()
        self.update()

    def set_target(self, target: QWidget | None) -> None:
        self._target = target
        self._reposition_panel()
        self.update()

    def refresh(self) -> None:
        self._sync_geometry()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        if event.key() in {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space}:
            self.next_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        target_rect = self._target_rect()
        overlay_path = QPainterPath()
        overlay_path.addRect(QRectF(self.rect()))

        if target_rect is not None:
            spotlight_rect = QRectF(target_rect.adjusted(-8, -8, 8, 8))
            highlight_path = QPainterPath()
            highlight_path.addRoundedRect(spotlight_rect, 18, 18)
            overlay_path = overlay_path.subtracted(highlight_path)

        painter.fillPath(overlay_path, QColor(15, 23, 42, 82))

        if target_rect is not None:
            painter.setPen(QPen(QColor("#60A5FA"), 3))
            painter.setBrush(QColor(255, 255, 255, 18))
            painter.drawRoundedRect(target_rect.adjusted(-4, -4, 4, 4), 16, 16)

    def _sync_geometry(self) -> None:
        self.setGeometry(self._host.rect())
        self._reposition_panel()

    def _target_rect(self) -> QRect | None:
        if self._target is None or not self._target.isVisible():
            return None
        top_left = self._target.mapTo(self._host, QPoint(0, 0))
        return QRect(top_left, self._target.size())

    def _reposition_panel(self) -> None:
        self.panel.adjustSize()
        width = min(max(self.panel.sizeHint().width(), 320), 360)
        self.panel.resize(width, self.panel.sizeHint().height())

        target_rect = self._target_rect()
        margin = 22
        gap = 18
        safe_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        if target_rect is None:
            x = self.width() - self.panel.width() - margin
            y = self.height() - self.panel.height() - margin
            self.panel.move(max(margin, x), max(margin, y))
            return

        available_right = safe_rect.right() - target_rect.right()
        available_left = target_rect.left() - safe_rect.left()
        available_below = safe_rect.bottom() - target_rect.bottom()
        available_above = target_rect.top() - safe_rect.top()

        # Prefer placements that keep the coachmark fully outside the highlighted area.
        candidates: list[QPoint] = []
        vertical_anchor = min(
            max(safe_rect.top(), target_rect.top()),
            safe_rect.bottom() - self.panel.height(),
        )
        horizontal_anchor = min(
            max(safe_rect.left(), target_rect.left()),
            safe_rect.right() - self.panel.width(),
        )

        if available_right >= self.panel.width() + gap:
            candidates.append(QPoint(target_rect.right() + gap, vertical_anchor))
        if available_left >= self.panel.width() + gap:
            candidates.append(
                QPoint(target_rect.left() - self.panel.width() - gap, vertical_anchor)
            )
        if available_above >= self.panel.height() + gap:
            candidates.append(
                QPoint(horizontal_anchor, target_rect.top() - self.panel.height() - gap)
            )
        if available_below >= self.panel.height() + gap:
            candidates.append(QPoint(horizontal_anchor, target_rect.bottom() + gap))

        for point in candidates:
            panel_rect = QRect(point, self.panel.size())
            if safe_rect.contains(panel_rect) and not panel_rect.intersects(
                target_rect.adjusted(-gap, -gap, gap, gap)
            ):
                self.panel.move(point)
                return

        # If there is no perfect fit, choose the position with the smallest overlap.
        fallback_candidates = [
            QPoint(
                min(
                    max(safe_rect.left(), target_rect.right() + gap),
                    safe_rect.right() - self.panel.width(),
                ),
                vertical_anchor,
            ),
            QPoint(
                max(safe_rect.left(), target_rect.left() - self.panel.width() - gap),
                vertical_anchor,
            ),
            QPoint(
                horizontal_anchor,
                max(safe_rect.top(), target_rect.top() - self.panel.height() - gap),
            ),
            QPoint(
                horizontal_anchor,
                min(
                    max(safe_rect.top(), target_rect.bottom() + gap),
                    safe_rect.bottom() - self.panel.height(),
                ),
            ),
        ]
        target_with_gap = target_rect.adjusted(-gap, -gap, gap, gap)
        best_point = fallback_candidates[0]
        best_score: tuple[int, int] | None = None
        for point in fallback_candidates:
            panel_rect = QRect(point, self.panel.size())
            intersection = panel_rect.intersected(target_with_gap)
            overlap_area = max(0, intersection.width()) * max(0, intersection.height())
            distance_score = abs(panel_rect.center().x() - target_rect.center().x()) + abs(
                panel_rect.center().y() - target_rect.center().y()
            )
            score = (overlap_area, distance_score)
            if best_score is None or score < best_score:
                best_score = score
                best_point = point
        self.panel.move(best_point)


class TutorialController(QObject):
    def __init__(
        self,
        window: QWidget,
        preferences: AppPreferences,
        templates: Callable[[], list[ProjectTemplate]],
        save_preferences: Callable[[], None],
        product_target: Callable[[], QWidget | None],
        template_target: Callable[[], QWidget | None],
        timeline_target: Callable[[], QWidget | None],
    ) -> None:
        super().__init__(window)
        self.window = window
        self.preferences = preferences
        self._templates = templates
        self._save_preferences = save_preferences
        self._product_target = product_target
        self._template_target = template_target
        self._timeline_target = timeline_target

        self._steps: list[TutorialStep] = []
        self._current_index = -1
        self._overlay: TutorialOverlay | None = None
        self._current_host: QWidget | None = None
        self._demo_dialog: BlockEditorDialog | None = None
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._steps = self._build_steps()
        self._current_index = 0
        self._show_current_step()

    def next_step(self) -> None:
        if not self._running:
            return
        current_step = self._steps[self._current_index]
        if current_step.on_exit is not None:
            current_step.on_exit(self)
        if self._current_index >= len(self._steps) - 1:
            self.finish(mark_seen=True)
            return
        self._current_index += 1
        self._show_current_step()

    def previous_step(self) -> None:
        if not self._running or self._current_index <= 0:
            return
        current_step = self._steps[self._current_index]
        if current_step.on_exit is not None:
            current_step.on_exit(self)
        self._current_index -= 1
        self._show_current_step()

    def finish(self, mark_seen: bool) -> None:
        if not self._running:
            return
        self._running = False
        self._close_demo_dialog()
        if self._overlay is not None:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None
        self._current_host = None
        if mark_seen and not self.preferences.tutorial_completed:
            self.preferences.tutorial_completed = True
            self._save_preferences()

    def _show_current_step(self) -> None:
        step = self._steps[self._current_index]
        if step.on_enter is not None:
            step.on_enter(self)

        host = step.host_resolver()
        if host is None:
            self.finish(mark_seen=False)
            return
        if self._overlay is None or self._current_host is not host:
            if self._overlay is not None:
                self._overlay.close()
                self._overlay.deleteLater()
            self._overlay = TutorialOverlay(host)
            self._overlay.next_requested.connect(self.next_step)
            self._overlay.previous_requested.connect(self.previous_step)
            self._overlay.close_requested.connect(
                lambda: self.finish(mark_seen=True)
            )
            self._current_host = host

        target = step.target_resolver()
        self._overlay.set_step(
            title=step.title,
            description=step.description,
            step_label=f"Schritt {self._current_index + 1} von {len(self._steps)}",
            is_first=self._current_index == 0,
            is_last=self._current_index == len(self._steps) - 1,
        )
        self._overlay.set_target(target)
        self._overlay.show()
        self._overlay.raise_()
        self._overlay.setFocus()

    def _build_steps(self) -> list[TutorialStep]:
        return [
            TutorialStep(
                title="Projektvorlagen anlegen",
                description=(
                    "Hier legst du eine Projektnummer an, setzt sie bei Bedarf als "
                    "Favorit und wählst eine Standardbemerkung. Diese Kombination "
                    "erspart dir später viele Klicks im Zeitblock-Dialog."
                ),
                host_resolver=lambda: self.window,
                target_resolver=self._template_target,
            ),
            TutorialStep(
                title="Zeitslot per Drag erfassen",
                description=(
                    "Im Zeitstrahl ziehst du mit der Maus einfach von Start bis Ende. "
                    "Sobald du loslässt, öffnet sich automatisch der Zeitblock-Dialog."
                ),
                host_resolver=lambda: self.window,
                target_resolver=self._timeline_target,
            ),
            TutorialStep(
                title="Projekt im Pop-up auswählen",
                description=(
                    "Im Dialog wählt man das Projekt aus der Liste oder direkt über "
                    "die Favoriten-Chips. Wenn eine Vorlage eine Standardbemerkung "
                    "hat, wird sie dabei direkt übernommen."
                ),
                host_resolver=lambda: self._demo_dialog,
                target_resolver=lambda: (
                    self._demo_dialog.project_section_widget
                    if self._demo_dialog is not None
                    else None
                ),
                on_enter=lambda controller: controller._ensure_demo_dialog(),
            ),
            TutorialStep(
                title="Bemerkung passend setzen",
                description=(
                    "Direkt darunter wählst du die Bemerkung aus. So ist jeder "
                    "Zeitblock sauber kategorisiert, zum Beispiel Admin, Meeting "
                    "oder Sys. Installation."
                ),
                host_resolver=lambda: self._demo_dialog,
                target_resolver=lambda: (
                    self._demo_dialog.remark_section_widget
                    if self._demo_dialog is not None
                    else None
                ),
            ),
            TutorialStep(
                title="Produktivzeit im Blick behalten",
                description=(
                    "Unten rechts siehst du jederzeit deine Produktivzeit, das Soll "
                    "und die Differenz. Damit kannst du vor dem Ausfüllen schnell "
                    "kontrollieren, ob der Tag stimmig ist."
                ),
                host_resolver=lambda: self.window,
                target_resolver=self._product_target,
                on_enter=lambda controller: controller._close_demo_dialog(),
            ),
        ]

    def _build_demo_dialog(self) -> BlockEditorDialog:
        templates = [ProjectTemplate.from_dict(item.to_dict()) for item in self._templates()]
        if not templates:
            templates = [
                ProjectTemplate(
                    project_number="25344",
                    display_name="Showroom",
                    default_remark="Sys. Installation",
                    is_favorite=True,
                ),
                ProjectTemplate(
                    project_number="27050",
                    display_name="Admin",
                    default_remark="Admin",
                    is_favorite=False,
                ),
            ]
        elif not any(item.is_favorite for item in templates):
            first = templates[0]
            templates[0] = ProjectTemplate.from_dict(
                {
                    **first.to_dict(),
                    "is_favorite": True,
                    "default_remark": first.default_remark or "Sys. Installation",
                }
            )

        sample_template = next((item for item in templates if item.is_favorite), templates[0])
        dialog_preferences = AppPreferences.from_dict(self.preferences.to_dict())
        dialog_preferences.last_project_number = sample_template.project_number
        dialog_preferences.last_work_remark = (
            sample_template.default_remark or dialog_preferences.last_work_remark
        )

        dialog = BlockEditorDialog(
            TimeBlock(
                date=getattr(self.window, "current_date", ""),
                start_time="08:00",
                end_time="10:00",
                block_type="work",
                project_number=sample_template.project_number,
                remark=sample_template.default_remark or "Sys. Installation",
            ),
            templates,
            dialog_preferences,
            is_new=True,
            parent=self.window,
        )
        dialog.setModal(False)
        dialog.finished.connect(lambda _result: self.finish(mark_seen=True))
        return dialog

    def _ensure_demo_dialog(self) -> None:
        if self._demo_dialog is None:
            self._demo_dialog = self._build_demo_dialog()
        self._demo_dialog.show()
        self._demo_dialog.raise_()
        self._demo_dialog.activateWindow()

    def _close_demo_dialog(self) -> None:
        if self._demo_dialog is None:
            return
        dialog = self._demo_dialog
        self._demo_dialog = None
        dialog.blockSignals(True)
        dialog.close()
        dialog.deleteLater()
