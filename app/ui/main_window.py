from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, timedelta

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.automation.runner import AutomationWorker
from app.automation.sequence import build_steps_for_blocks
from app.constants import APP_NAME
from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.services.day_service import DayService
from app.ui.block_editor import BlockEditorDialog
from app.ui.template_panel import ProjectTemplatesWidget
from app.ui.timeline_widget import DayTimelineWidget
from app.utils.time_utils import format_duration_minutes

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, service: DayService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.blocks: list[TimeBlock] = []
        self.templates: list[ProjectTemplate] = self.service.load_templates()
        self.preferences: AppPreferences = self.service.load_preferences()
        self.current_date = date.today().isoformat()
        self.countdown_remaining = 0
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.worker: AutomationWorker | None = None
        self.pending_steps = []

        self.setWindowTitle(APP_NAME)
        self.resize(920, 920)
        self.setMinimumSize(720, 820)
        self._build_ui()
        self._load_day(self.current_date)

    def closeEvent(self, event) -> None:
        self._persist_current_day()
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_abort()
            self.worker.wait(2000)
        super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        title = QLabel(APP_NAME)
        title.setObjectName("WindowTitle")
        toolbar.addWidget(title)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("VersionBadge")
        toolbar.addWidget(version_label)
        toolbar.addStretch()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.date_edit.setCalendarWidget(self._build_calendar_widget())

        today_button = QPushButton("Heute")
        today_button.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        save_button = QPushButton("Tag speichern")
        save_button.clicked.connect(self._persist_current_day)
        copy_button = QPushButton("Vortag kopieren")
        copy_button.clicked.connect(self._copy_previous_day)

        toolbar.addWidget(QLabel("Datum"))
        toolbar.addWidget(self.date_edit)
        toolbar.addWidget(today_button)
        toolbar.addWidget(copy_button)
        toolbar.addWidget(save_button)
        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        self.timeline = DayTimelineWidget()
        self.timeline.set_templates(self.templates)
        self.timeline.create_requested.connect(self._create_block_from_drag)
        self.timeline.edit_requested.connect(self._edit_block)
        self.timeline.move_or_resize_requested.connect(self._move_or_resize_block)
        self.timeline.action_requested.connect(self._handle_timeline_action)

        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(10)
        timeline_help = QLabel(
            "Drag erstellt neue Blöcke. Doppelklick bearbeitet. Kontextmenü löscht oder teilt."
        )
        timeline_help.setObjectName("HelpText")
        timeline_help.setWordWrap(True)
        timeline_layout.addWidget(timeline_help)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        scroll.setWidget(self.timeline)
        timeline_layout.addWidget(scroll, stretch=1)
        splitter.addWidget(timeline_container)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)

        self.templates_widget = ProjectTemplatesWidget()
        self.templates_widget.setObjectName("TemplatesPanel")
        self.templates_widget.set_templates(self.templates)
        self.templates_widget.templates_changed.connect(self._templates_updated)
        sidebar_layout.addWidget(self.templates_widget, stretch=4)

        validation_group = QGroupBox("Validierung")
        validation_layout = QVBoxLayout(validation_group)
        validation_layout.setContentsMargins(10, 14, 10, 10)
        self.validation_list = QListWidget()
        self.validation_list.setMinimumHeight(100)
        self.validation_list.setMaximumHeight(140)
        validation_layout.addWidget(self.validation_list)
        sidebar_layout.addWidget(validation_group)

        productivity_group = QGroupBox("Produktivzeit")
        productivity_layout = QVBoxLayout(productivity_group)
        productivity_layout.setContentsMargins(10, 14, 10, 10)
        self.productive_time_label = QLabel("Produktiv: 0:00")
        self.productive_target_label = QLabel("Soll: 0:00")
        self.productive_difference_label = QLabel("Differenz: 0:00")
        self.productive_difference_label.setObjectName("DifferenceLabel")
        productivity_layout.addWidget(self.productive_time_label)
        productivity_layout.addWidget(self.productive_target_label)
        productivity_layout.addWidget(self.productive_difference_label)
        sidebar_layout.addWidget(productivity_group)

        controls_group = QGroupBox("Automation")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setContentsMargins(10, 14, 10, 10)
        self.status_label = QLabel("bereit")
        self.status_label.setObjectName("StatusLabel")
        self.fill_button = QPushButton("Ausfüllen in Messerli")
        self.fill_button.setObjectName("PrimaryButton")
        self.fill_button.clicked.connect(self._prepare_fill)
        controls_layout.addWidget(self.status_label)
        controls_layout.addWidget(self.fill_button)
        sidebar_layout.addWidget(controls_group)
        sidebar_layout.addStretch()

        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([470, 430])

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #F4F6FB;
                color: #1E293B;
            }
            QLabel {
                color: #1E293B;
                background: transparent;
            }
            QLabel#WindowTitle {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#VersionBadge {
                color: #475569;
                background: #E2E8F0;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#HelpText {
                color: #475569;
                padding: 0 2px 2px 2px;
            }
            QLabel#StatusLabel {
                color: #334155;
                font-weight: 600;
            }
            QLabel#DifferenceLabel {
                font-weight: 700;
            }
            QGroupBox {
                border: 1px solid #D7DFEC;
                border-radius: 14px;
                margin-top: 12px;
                font-weight: 600;
                color: #1E293B;
                background: #FCFDFE;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #0F172A;
                background: #F4F6FB;
            }
            QListWidget, QLineEdit, QComboBox, QDateEdit, QTimeEdit, QScrollArea {
                border: 1px solid #C9D4E5;
                border-radius: 10px;
                padding: 6px;
                background: #FFFFFF;
                color: #1E293B;
                selection-background-color: #DBEAFE;
                selection-color: #0F172A;
            }
            QListWidget::item {
                padding: 6px 4px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: #DBEAFE;
                color: #0F172A;
            }
            QPushButton {
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 8px 12px;
                background: #FFFFFF;
                color: #0F172A;
                font-weight: 500;
            }
            QPushButton:hover { background: #F8FAFC; border-color: #94A3B8; }
            QPushButton:pressed { background: #EEF2FF; }
            QPushButton:checked {
                background: #DBEAFE;
                border-color: #60A5FA;
                color: #1D4ED8;
                font-weight: 600;
            }
            QPushButton#PrimaryButton {
                background: #E0F2FE;
                border-color: #38BDF8;
                color: #0F172A;
                font-weight: 600;
            }
            QPushButton#PrimaryButton:hover { background: #BAE6FD; }
            QPushButton:disabled {
                background: #E2E8F0;
                color: #94A3B8;
                border-color: #CBD5E1;
            }
            QComboBox QAbstractItemView {
                background: #FFFFFF;
                color: #1E293B;
                selection-background-color: #DBEAFE;
                selection-color: #0F172A;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #EFF6FF;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #1E293B;
                background-color: #FFFFFF;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                outline: 0;
            }
            QCalendarWidget QToolButton {
                color: #0F172A;
                background: transparent;
                border: none;
                margin: 4px;
                padding: 6px 8px;
                border-radius: 8px;
            }
            QCalendarWidget QToolButton:hover {
                background: #E2E8F0;
            }
            QCalendarWidget QMenu {
                background: #FFFFFF;
                color: #1E293B;
            }
            QCalendarWidget QSpinBox {
                background: #FFFFFF;
                color: #1E293B;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QSplitter::handle {
                background: #D7DFEC;
                width: 6px;
                margin: 8px 0;
                border-radius: 3px;
            }
            """
        )

    def _build_calendar_widget(self) -> QCalendarWidget:
        calendar = QCalendarWidget(self)
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#DCFCE7"))
        today_format.setForeground(QColor("#166534"))
        calendar.setDateTextFormat(QDate.currentDate(), today_format)
        return calendar

    def _on_date_changed(self, qdate: QDate) -> None:
        new_date = qdate.toPython().isoformat()
        if new_date == self.current_date:
            return
        self._persist_current_day()
        self._load_day(new_date)

    def _load_day(self, day: str) -> None:
        self.current_date = day
        self.blocks = self.service.load_day(day)
        self.timeline.set_blocks(self.blocks)
        self._refresh_lists()
        qdate = QDate.fromString(day, "yyyy-MM-dd")
        if qdate.isValid() and self.date_edit.date() != qdate:
            self.date_edit.blockSignals(True)
            self.date_edit.setDate(qdate)
            self.date_edit.blockSignals(False)
        self._set_status("bereit")
        logger.info("Loaded day %s with %s blocks", day, len(self.blocks))

    def _persist_current_day(self) -> None:
        self.service.save_day(self.current_date, self.blocks)
        self.service.save_preferences(self.preferences)
        logger.info("Saved day %s", self.current_date)

    def _refresh_lists(self) -> None:
        self.timeline.set_blocks(self.blocks)
        issues = self.service.validate_day(self.blocks)
        self.validation_list.clear()
        if issues:
            for issue in issues:
                self.validation_list.addItem(issue.message)
        else:
            self.validation_list.addItem("Keine Validierungsfehler.")

        summary = self.service.productive_time_summary(self.current_date, self.blocks)
        self.productive_time_label.setText(
            f"Produktiv: {format_duration_minutes(summary.productive_minutes)}"
        )
        self.productive_target_label.setText(
            f"Soll: {format_duration_minutes(summary.target_minutes)}"
        )
        self.productive_difference_label.setText(
            f"Differenz: {format_duration_minutes(summary.difference_minutes, include_sign=True)}"
        )
        if summary.difference_minutes < 0:
            self.productive_difference_label.setStyleSheet("color: #B91C1C;")
        elif summary.difference_minutes > 0:
            self.productive_difference_label.setStyleSheet("color: #166534;")
        else:
            self.productive_difference_label.setStyleSheet("color: #334155;")

        self.fill_button.setEnabled(
            bool(self.blocks) and not issues and self.worker is None
        )

    def _create_block_from_drag(self, start_time: str, end_time: str) -> None:
        block = TimeBlock(
            date=self.current_date,
            start_time=start_time,
            end_time=end_time,
            block_type="work",
            project_number=self.preferences.last_project_number,
            remark=self.preferences.last_work_remark,
        )
        dialog = BlockEditorDialog(
            block, self.templates, self.preferences, is_new=True, parent=self
        )
        if dialog.exec() and dialog.result_block:
            self.blocks.append(dialog.result_block)
            self._remember_preferences(dialog.result_block)
            self._persist_current_day()
            self._refresh_lists()

    def _edit_block(self, block_id: str) -> None:
        block = self._find_block(block_id)
        if block is None:
            return
        dialog = BlockEditorDialog(
            block, self.templates, self.preferences, is_new=False, parent=self
        )
        if not dialog.exec():
            return

        if dialog.result_action == "delete":
            self.blocks = [item for item in self.blocks if item.id != block_id]
        elif dialog.result_action == "split" and dialog.result_block:
            self._split_block(dialog.result_block)
        elif dialog.result_action == "save" and dialog.result_block:
            self.blocks = [
                dialog.result_block if item.id == block_id else item
                for item in self.blocks
            ]
            self._remember_preferences(dialog.result_block)

        self._persist_current_day()
        self._refresh_lists()

    def _move_or_resize_block(
        self, block_id: str, start_time: str, end_time: str
    ) -> None:
        block = self._find_block(block_id)
        if block is None:
            return
        updated = replace(block, start_time=start_time, end_time=end_time)
        self.blocks = [updated if item.id == block_id else item for item in self.blocks]
        self._persist_current_day()
        self._refresh_lists()

    def _handle_timeline_action(self, action: str, block_id: str) -> None:
        block = self._find_block(block_id)
        if block is None:
            return
        if action == "delete":
            self.blocks = [item for item in self.blocks if item.id != block_id]
        elif action == "split":
            self._split_block(block)
        self._persist_current_day()
        self._refresh_lists()

    def _split_block(self, block: TimeBlock) -> None:
        try:
            first, second = self.service.split_block(block)
        except ValueError as exc:
            QMessageBox.warning(self, "Block teilen", str(exc))
            return
        self.blocks = [item for item in self.blocks if item.id != block.id]
        self.blocks.extend([first, second])

    def _templates_updated(self, templates: list[ProjectTemplate]) -> None:
        self.templates = templates
        self.service.save_templates(templates)
        self.timeline.set_templates(templates)
        self._refresh_lists()
        logger.info("Updated %s templates", len(templates))

    def _prepare_fill(self) -> None:
        issues = self.service.validate_day(self.blocks)
        if issues:
            QMessageBox.warning(
                self, "Validierung", "\n".join(issue.message for issue in issues)
            )
            return

        self.pending_steps = build_steps_for_blocks(self.blocks)
        message = (
            "Bitte jetzt das erste leere Auftragsfeld in Messerli anklicken.\n\n"
            "Nach dem Bestätigen startet ein 3-Sekunden-Countdown. ESC bricht sofort ab."
        )
        response = QMessageBox.question(
            self,
            "Ausfüllen vorbereiten",
            message,
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok,
        )
        if response != QMessageBox.Ok:
            return

        self.countdown_remaining = max(1, self.preferences.countdown_seconds)
        self.fill_button.setEnabled(False)
        self._set_status(f"Countdown läuft: {self.countdown_remaining}")
        self.countdown_timer.start(1000)

    def _countdown_tick(self) -> None:
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self._set_status(f"Countdown läuft: {self.countdown_remaining}")
            return
        self.countdown_timer.stop()
        self._start_automation()

    def _start_automation(self) -> None:
        self.worker = AutomationWorker(
            self.pending_steps, typing_interval=self.preferences.typing_interval
        )
        self.worker.status_changed.connect(self._set_status)
        self.worker.completed.connect(self._automation_completed)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def _automation_completed(self, success: bool, message: str) -> None:
        self._set_status(message)
        if success:
            QMessageBox.information(
                self, "Automation", "Die Einträge wurden abgeschlossen."
            )
        elif message == "abgebrochen":
            QMessageBox.warning(self, "Automation", "Die Eingabe wurde abgebrochen.")
        else:
            QMessageBox.critical(self, "Automation", message)

    def _cleanup_worker(self) -> None:
        self.worker = None
        self._refresh_lists()

    def _remember_preferences(self, block: TimeBlock) -> None:
        if block.block_type == "work":
            self.preferences.last_project_number = block.project_number
            self.preferences.last_work_remark = block.remark

    def _copy_previous_day(self) -> None:
        current = date.fromisoformat(self.current_date)
        previous = (current - timedelta(days=1)).isoformat()
        previous_blocks = self.service.load_day(previous)
        if not previous_blocks:
            QMessageBox.information(
                self,
                "Vortag kopieren",
                "Für den Vortag wurden keine Einträge gefunden.",
            )
            return
        self.blocks = [
            TimeBlock(
                date=self.current_date,
                start_time=block.start_time,
                end_time=block.end_time,
                block_type=block.block_type,
                project_number=block.project_number,
                remark=block.remark,
            )
            for block in previous_blocks
        ]
        self._persist_current_day()
        self._refresh_lists()
        self._set_status("bereit")

    def _find_block(self, block_id: str) -> TimeBlock | None:
        return next((item for item in self.blocks if item.id == block_id), None)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
