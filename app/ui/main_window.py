from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.automation.runner import AutomationWorker
from app.automation.sequence import build_steps_for_blocks
from app.constants import (
    APP_ALWAYS_SHOW_TUTORIAL_ON_START,
    APP_NAME,
    BLOCK_TYPE_BREAK,
    BLOCK_TYPE_WORK,
    TIMELINE_DEFAULT_VISIBLE_HOUR,
)
from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.services.day_service import DayService
from app.services.update_service import (
    AppUpdate,
    GitHubReleaseUpdater,
    UpdateCheckResult,
    UpdateError,
)
from app.ui.block_editor import BlockEditorDialog
from app.ui.template_panel import ProjectTemplatesWidget
from app.ui.timeline_widget import DayTimelineWidget
from app.ui.tutorial import TutorialController
from app.ui.update_workers import UpdateCheckWorker, UpdateDownloadWorker
from app.utils.paths import get_bundle_dir
from app.utils.time_utils import format_duration_minutes
from app.utils.windows import (
    activate_window,
    get_foreground_window_handle,
    is_current_process_window,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: DayService,
        updater: GitHubReleaseUpdater | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.updater = updater
        self.blocks: list[TimeBlock] = []
        self.templates: list[ProjectTemplate] = self.service.load_templates()
        self.preferences: AppPreferences = self.service.load_preferences()
        self.service.sync_project_badge_assignments(self.templates, self.preferences)
        self.current_date = date.today().isoformat()
        self.countdown_remaining = 0
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.day_action_status_timer = QTimer(self)
        self.day_action_status_timer.setSingleShot(True)
        self.day_action_status_timer.timeout.connect(
            lambda: self._set_day_action_status("")
        )
        self.lunch_expenses_notice_timer = QTimer(self)
        self.lunch_expenses_notice_timer.setSingleShot(True)
        self.lunch_expenses_notice_timer.timeout.connect(
            lambda: self._set_lunch_expenses_notice("")
        )
        self.worker: AutomationWorker | None = None
        self.update_check_worker: UpdateCheckWorker | None = None
        self.update_download_worker: UpdateDownloadWorker | None = None
        self.update_progress_dialog: QProgressDialog | None = None
        self.pending_update: AppUpdate | None = None
        self.pending_steps = []
        self._lunch_expenses_manual_override = False
        self._updating_lunch_expenses_checkbox = False
        self.tutorial_controller: TutorialController | None = None
        self._tutorial_start_scheduled = False
        self._copied_day_blocks: list[TimeBlock] = []
        self._copied_day_source_date: str | None = None
        self._calendar_selected_date = QDate.currentDate()

        self.setWindowTitle(APP_NAME)
        self.resize(920, 920)
        self.setMinimumSize(720, 820)
        self._build_ui()
        self._load_day(self.current_date)
        if self.updater is not None:
            QTimer.singleShot(1500, self._check_for_updates_in_background)

    def closeEvent(self, event) -> None:
        if (
            self.update_download_worker is not None
            and self.update_download_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Update",
                "Der Update-Download läuft noch. Bitte warte einen Moment.",
            )
            event.ignore()
            return
        self._persist_current_day()
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_abort()
            self.worker.wait(2000)
        if (
            self.update_check_worker is not None
            and self.update_check_worker.isRunning()
        ):
            self.update_check_worker.wait(2000)
        super().closeEvent(event)

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        activate_window(int(self.winId()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._position_day_action_status()
        self._position_lunch_expenses_notice()
        if self._tutorial_start_scheduled or (
            not APP_ALWAYS_SHOW_TUTORIAL_ON_START
            and self.preferences.tutorial_completed
        ):
            return
        self._tutorial_start_scheduled = True
        QTimer.singleShot(600, self._auto_start_tutorial)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_day_action_status()
        self._position_lunch_expenses_notice()

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
        self.update_button = QPushButton("Nach Updates suchen")
        self.update_button.setObjectName("UpdateButton")
        self.update_button.clicked.connect(self._check_for_updates_manually)
        self.update_button.setEnabled(self.updater is not None)
        toolbar.addWidget(self.update_button)
        self.tutorial_button = QPushButton("Einführung")
        self.tutorial_button.clicked.connect(self.start_tutorial)
        toolbar.addWidget(self.tutorial_button)
        toolbar.addStretch()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.calendar_widget = self._build_calendar_widget()
        self.date_edit.setCalendarWidget(self.calendar_widget)

        previous_day_button = QToolButton()
        previous_day_button.setObjectName("DayNavButton")
        previous_day_button.setArrowType(Qt.LeftArrow)
        previous_day_button.setAutoRaise(True)
        previous_day_button.clicked.connect(lambda: self._shift_current_day(-1))

        next_day_button = QToolButton()
        next_day_button.setObjectName("DayNavButton")
        next_day_button.setArrowType(Qt.RightArrow)
        next_day_button.setAutoRaise(True)
        next_day_button.clicked.connect(lambda: self._shift_current_day(1))

        today_button = QPushButton("Heute")
        today_button.clicked.connect(
            lambda: self.date_edit.setDate(QDate.currentDate())
        )
        self.copy_day_action = QAction("Diesen Tag kopieren", self)
        self.copy_day_action.triggered.connect(self._copy_current_day)
        self.paste_day_action = QAction("Einfügen", self)
        self.paste_day_action.triggered.connect(self._paste_copied_day)
        self.paste_previous_day_action = QAction("Vortag einfügen", self)
        self.paste_previous_day_action.triggered.connect(self._paste_previous_day)

        copy_paste_menu = QMenu(self)
        copy_paste_menu.addAction(self.copy_day_action)
        copy_paste_menu.addAction(self.paste_day_action)
        copy_paste_menu.addAction(self.paste_previous_day_action)

        self.copy_paste_button = QToolButton()
        self.copy_paste_button.setObjectName("ToolbarMenuButton")
        self.copy_paste_button.setText("Copy/Paste")
        self.copy_paste_button.setPopupMode(QToolButton.InstantPopup)
        self.copy_paste_button.setMenu(copy_paste_menu)
        self._update_copy_paste_actions()

        date_nav_widget = QWidget()
        date_nav_layout = QHBoxLayout(date_nav_widget)
        date_nav_layout.setContentsMargins(0, 0, 0, 0)
        date_nav_layout.setSpacing(2)
        date_nav_layout.addWidget(previous_day_button)
        date_nav_layout.addWidget(self.date_edit)
        date_nav_layout.addWidget(next_day_button)

        toolbar.addWidget(QLabel("Datum"))
        toolbar.addWidget(date_nav_widget)
        toolbar.addWidget(today_button)
        toolbar.addWidget(self.copy_paste_button)
        main_layout.addLayout(toolbar)

        self.day_action_status_label = QLabel("", self)
        self.day_action_status_label.setObjectName("ToolbarStatusLabel")
        self.day_action_status_label.setWordWrap(False)
        self.day_action_status_label.setAutoFillBackground(False)
        self.day_action_status_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.day_action_status_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.day_action_status_label.setAttribute(Qt.WA_NoSystemBackground, True)
        self.day_action_status_label.setVisible(False)

        self.lunch_expenses_notice_label = QLabel("", self)
        self.lunch_expenses_notice_label.setObjectName("LunchExpensesNotice")
        self.lunch_expenses_notice_label.setWordWrap(True)
        self.lunch_expenses_notice_label.setMaximumWidth(320)
        self.lunch_expenses_notice_label.setAttribute(
            Qt.WA_TransparentForMouseEvents, True
        )
        self.lunch_expenses_notice_label.setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        self.timeline = DayTimelineWidget()
        self.timeline.set_templates(self.templates)
        self.timeline.set_project_badge_assignments(
            self.preferences.project_badge_assignments
        )
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

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(False)
        self.timeline_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.timeline_scroll.setWidget(self.timeline)
        timeline_layout.addWidget(self.timeline_scroll, stretch=1)
        splitter.addWidget(timeline_container)
        self.timeline_container = timeline_container
        QTimer.singleShot(0, self._scroll_timeline_to_default_hour)

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
        self.productivity_group = productivity_group
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
        self.lunch_expenses_checkbox = QCheckBox("Inkl. Mittagspesen")
        checked_icon = (
            get_bundle_dir() / "app" / "ui" / "assets" / "checkbox_checked.svg"
        ).as_posix()
        self.lunch_expenses_checkbox.setStyleSheet(
            """
            QCheckBox {
                spacing: 10px;
                padding: 2px 0;
                background: transparent;
                color: #0F172A;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 1px solid #94A3B8;
                border-radius: 5px;
                background: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                image: url("%s");
                background: transparent;
                border: none;
            }
            QCheckBox::indicator:unchecked:hover,
            QCheckBox::indicator:checked:hover {
                border: 1px solid #60A5FA;
            }
            """
            % checked_icon
        )
        self.lunch_expenses_checkbox.stateChanged.connect(
            self._lunch_expenses_checkbox_changed
        )
        self.fill_button = QPushButton("Ausfüllen in Messerli")
        self.fill_button.setObjectName("PrimaryButton")
        self.fill_button.clicked.connect(self._prepare_fill)
        fill_options_layout = QHBoxLayout()
        fill_options_layout.setContentsMargins(0, 0, 0, 0)
        fill_options_layout.setSpacing(10)
        fill_options_layout.addWidget(self.lunch_expenses_checkbox)
        fill_options_layout.addWidget(self.fill_button, stretch=1)
        controls_layout.addWidget(self.status_label)
        controls_layout.addLayout(fill_options_layout)
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
            QLabel#ToolbarStatusLabel {
                color: #475569;
                background: transparent;
                background-color: rgba(0, 0, 0, 0);
                border: none;
                padding: 0;
                font-size: 11px;
            }
            QLabel#LunchExpensesNotice {
                color: #0F172A;
                background: #FFFFFF;
                border: 1px solid #F59E0B;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 600;
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
            QToolButton#ToolbarMenuButton {
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 8px 28px 8px 12px;
                background: #FFFFFF;
                color: #0F172A;
                font-weight: 500;
            }
            QToolButton#ToolbarMenuButton:hover {
                background: #F8FAFC;
                border-color: #94A3B8;
            }
            QToolButton#ToolbarMenuButton:pressed {
                background: #EEF2FF;
            }
            QToolButton#ToolbarMenuButton:disabled {
                background: #E2E8F0;
                color: #94A3B8;
                border-color: #CBD5E1;
            }
            QToolButton#ToolbarMenuButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                left: -8px;
            }
            QToolButton#DayNavButton {
                border: none;
                border-radius: 8px;
                padding: 6px;
                min-width: 14px;
                min-height: 14px;
                background: transparent;
                color: #475569;
            }
            QToolButton#DayNavButton:hover {
                background: #E2E8F0;
                color: #0F172A;
            }
            QToolButton#DayNavButton:pressed {
                background: #CBD5E1;
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
        self._create_tutorial_controller()

    def _build_calendar_widget(self) -> QCalendarWidget:
        calendar = QCalendarWidget(self)
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self._update_calendar_formats(calendar, self.date_edit.date())
        return calendar

    def _update_calendar_formats(
        self, calendar: QCalendarWidget, selected_date: QDate
    ) -> None:
        default_format = QTextCharFormat()
        today = QDate.currentDate()
        if selected_date.isValid():
            calendar.setSelectedDate(selected_date)

        if self._calendar_selected_date.isValid():
            calendar.setDateTextFormat(self._calendar_selected_date, default_format)
        calendar.setDateTextFormat(today, default_format)

        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#DCFCE7"))
        today_format.setForeground(QColor("#166534"))
        today_format.setFontWeight(600)

        selected_format = QTextCharFormat()
        selected_format.setBackground(QColor("#DBEAFE"))
        selected_format.setForeground(QColor("#1D4ED8"))
        selected_format.setFontWeight(600)

        selected_today_format = QTextCharFormat()
        selected_today_format.setBackground(QColor("#BBF7D0"))
        selected_today_format.setForeground(QColor("#166534"))
        selected_today_format.setFontWeight(700)

        if selected_date == today:
            calendar.setDateTextFormat(today, selected_today_format)
        else:
            calendar.setDateTextFormat(today, today_format)
            if selected_date.isValid():
                calendar.setDateTextFormat(selected_date, selected_format)

        self._calendar_selected_date = selected_date

    def _create_tutorial_controller(self) -> None:
        self.tutorial_controller = TutorialController(
            window=self,
            preferences=self.preferences,
            templates=lambda: self.templates,
            save_preferences=self._save_preferences_only,
            project_list_target=lambda: self.templates_widget.list_widget,
            product_target=lambda: self.productivity_group,
            template_target=lambda: getattr(self.templates_widget, "form_group", None),
            timeline_target=lambda: self.timeline_scroll,
            fill_target=lambda: self.fill_button,
        )

    def _save_preferences_only(self) -> None:
        self.service.save_preferences(self.preferences)

    def _shift_current_day(self, offset_days: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(offset_days))

    def _auto_start_tutorial(self) -> None:
        if not self.isVisible():
            return
        if (
            not APP_ALWAYS_SHOW_TUTORIAL_ON_START
            and self.preferences.tutorial_completed
        ):
            return
        self.start_tutorial()

    def start_tutorial(self) -> None:
        if self.tutorial_controller is None or self.tutorial_controller.is_running():
            return
        self.bring_to_front()
        self.tutorial_controller.start()

    def _on_date_changed(self, qdate: QDate) -> None:
        self._update_calendar_formats(self.calendar_widget, qdate)
        new_date = qdate.toPython().isoformat()
        if new_date == self.current_date:
            return
        self._persist_current_day()
        self._load_day(new_date)

    def _load_day(self, day: str) -> None:
        self.current_date = day
        self._lunch_expenses_manual_override = False
        self.blocks = self.service.load_day(day)
        self.timeline.set_blocks(self.blocks)
        self._refresh_lists()
        qdate = QDate.fromString(day, "yyyy-MM-dd")
        if qdate.isValid() and self.date_edit.date() != qdate:
            self.date_edit.blockSignals(True)
            self.date_edit.setDate(qdate)
            self.date_edit.blockSignals(False)
        self._update_calendar_formats(self.calendar_widget, qdate)
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
        self.lunch_expenses_checkbox.setEnabled(self.worker is None)
        self._update_lunch_expenses_checkbox()

    def _lunch_expenses_checkbox_changed(self, _state: int) -> None:
        if self._updating_lunch_expenses_checkbox:
            return
        self._lunch_expenses_manual_override = True
        self._show_lunch_expenses_warning()

    def _update_lunch_expenses_checkbox(self) -> None:
        if self._lunch_expenses_manual_override:
            return
        self._updating_lunch_expenses_checkbox = True
        try:
            self.lunch_expenses_checkbox.setChecked(
                self._should_include_lunch_expenses()
            )
        finally:
            self._updating_lunch_expenses_checkbox = False

    def _should_include_lunch_expenses(self) -> bool:
        return self._has_eligible_drive() and self._has_lunch_break()

    def _has_eligible_drive(self) -> bool:
        has_eligible_drive = False
        for block in self.blocks:
            if block.block_type != BLOCK_TYPE_WORK or block.remark != "Fahrt":
                continue
            try:
                if block.duration_minutes >= 15:
                    has_eligible_drive = True
                    break
            except ValueError:
                continue
        return has_eligible_drive

    def _has_lunch_break(self) -> bool:
        return any(
            block.block_type == BLOCK_TYPE_BREAK and block.remark == "Mittag"
            for block in self.blocks
        )

    def _show_lunch_expenses_warning(self) -> None:
        message = ""
        if self.lunch_expenses_checkbox.isChecked():
            if not self._has_lunch_break():
                message = (
                    "Mittagspesen ist aktiviert, aber es wurde kein Mittag-Block "
                    "gefunden."
                )
            elif not self._has_eligible_drive():
                message = "Mittagspesen ist aktiviert aber keine Fahrt wurde eingetragen!"
        if message:
            self._set_lunch_expenses_notice(message)

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
        self.service.sync_project_badge_assignments(self.templates, self.preferences)
        self.service.save_preferences(self.preferences)
        self.timeline.set_templates(templates)
        self.timeline.set_project_badge_assignments(
            self.preferences.project_badge_assignments
        )
        self._refresh_lists()
        logger.info("Updated %s templates", len(templates))

    def _check_for_updates_in_background(self) -> None:
        self._start_update_check(manual=False)

    def _check_for_updates_manually(self) -> None:
        self._start_update_check(manual=True)

    def _start_update_check(self, manual: bool) -> None:
        if self.updater is None:
            if manual:
                QMessageBox.information(
                    self,
                    "Updates",
                    "Für diese App ist noch kein Update-Service konfiguriert.",
                )
            return
        if (
            self.update_check_worker is not None
            and self.update_check_worker.isRunning()
        ):
            if manual:
                QMessageBox.information(
                    self,
                    "Updates",
                    "Die Update-Prüfung läuft bereits.",
                )
            return

        if manual:
            self._set_status("Prüfe auf Updates ...")
        self.update_button.setEnabled(False)
        self.update_check_worker = UpdateCheckWorker(self.updater, manual, self)
        self.update_check_worker.completed.connect(self._handle_update_check_result)
        self.update_check_worker.finished.connect(self._cleanup_update_check_worker)
        self.update_check_worker.start()

    def _handle_update_check_result(self, result_obj: object, manual: bool) -> None:
        if not isinstance(result_obj, UpdateCheckResult):
            return
        result = result_obj

        if result.error:
            if manual:
                self._set_status("Update-Prüfung fehlgeschlagen")
                QMessageBox.warning(self, "Updates", result.error)
            else:
                logger.warning("Background update check failed: %s", result.error)
            return

        if not result.update_available or result.update is None:
            if manual:
                self._set_status("App ist aktuell")
                QMessageBox.information(
                    self,
                    "Updates",
                    f"Es ist keine neuere Version als v{__version__} verfügbar.",
                )
            else:
                logger.info("No newer version available")
            return

        update = result.update
        if not manual and self.preferences.skipped_update_version == update.version:
            logger.info(
                "Skipped update %s because user ignored it earlier", update.version
            )
            return

        self.pending_update = update
        self._show_update_prompt(update, manual)

    def _cleanup_update_check_worker(self) -> None:
        self.update_check_worker = None
        if self.update_download_worker is None:
            self.update_button.setEnabled(self.updater is not None)

    def _show_update_prompt(self, update: AppUpdate, manual: bool) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Update verfügbar")
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(
            f"Version {update.version} ist verfügbar.\n\n"
            "Der Installer wird direkt aus GitHub Releases heruntergeladen."
        )
        dialog.setInformativeText(
            "Nach dem Download startet das Setup und die App wird beendet."
        )
        if update.notes:
            dialog.setDetailedText(update.notes)

        install_button = dialog.addButton("Jetzt aktualisieren", QMessageBox.AcceptRole)
        later_button = dialog.addButton("Später", QMessageBox.RejectRole)
        skip_button = None
        if not manual:
            skip_button = dialog.addButton(
                "Diese Version überspringen",
                QMessageBox.DestructiveRole,
            )
        dialog.setDefaultButton(install_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == install_button:
            self.preferences.skipped_update_version = ""
            self.service.save_preferences(self.preferences)
            self._download_update(update)
            return
        if skip_button is not None and clicked == skip_button:
            self.preferences.skipped_update_version = update.version
            self.service.save_preferences(self.preferences)
            self._set_status(f"Update {update.version} übersprungen")
            return
        if clicked == later_button and manual:
            self._set_status("Update später")

    def _download_update(self, update: AppUpdate) -> None:
        if self.updater is None:
            return
        if (
            self.update_download_worker is not None
            and self.update_download_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Update",
                "Ein Update wird bereits heruntergeladen.",
            )
            return

        self.pending_update = update
        self.update_button.setEnabled(False)
        self.update_progress_dialog = QProgressDialog(
            "Installer wird von GitHub Releases heruntergeladen ...",
            "",
            0,
            0,
            self,
        )
        self.update_progress_dialog.setWindowTitle("Update herunterladen")
        self.update_progress_dialog.setAutoClose(False)
        self.update_progress_dialog.setAutoReset(False)
        self.update_progress_dialog.setCancelButton(None)
        self.update_progress_dialog.setMinimumDuration(0)
        self.update_progress_dialog.setWindowModality(Qt.WindowModal)
        self.update_progress_dialog.show()

        self.update_download_worker = UpdateDownloadWorker(self.updater, update, self)
        self.update_download_worker.progress_changed.connect(
            self._update_download_progress
        )
        self.update_download_worker.completed.connect(self._update_download_completed)
        self.update_download_worker.failed.connect(self._update_download_failed)
        self.update_download_worker.finished.connect(
            self._cleanup_update_download_worker
        )
        self.update_download_worker.start()

    def _update_download_progress(self, downloaded: int, total: int) -> None:
        if self.update_progress_dialog is None:
            return
        if total > 0:
            self.update_progress_dialog.setRange(0, total)
            self.update_progress_dialog.setValue(downloaded)
            self.update_progress_dialog.setLabelText(
                "Installer wird von GitHub Releases heruntergeladen ...\n"
                f"{self._format_megabytes(downloaded)} / {self._format_megabytes(total)}"
            )
            return
        self.update_progress_dialog.setRange(0, 0)

    def _update_download_completed(self, installer_path: str) -> None:
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        if self.updater is None:
            return

        QMessageBox.information(
            self,
            "Update bereit",
            "Der Installer wurde heruntergeladen. Nach dem Schliessen dieses Dialogs "
            "startet das Setup und die App beendet sich.",
        )

        try:
            self.updater.launch_installer(Path(installer_path))
        except UpdateError as exc:
            QMessageBox.critical(self, "Update", str(exc))
            self._set_status("Installer konnte nicht gestartet werden")
            return

        self._set_status("Update wird installiert")
        QTimer.singleShot(0, QApplication.instance().quit)

    def _update_download_failed(self, message: str) -> None:
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        self._set_status("Update-Download fehlgeschlagen")
        QMessageBox.critical(self, "Update", message)

    def _cleanup_update_download_worker(self) -> None:
        self.update_download_worker = None
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.close()
            self.update_progress_dialog = None
        self.update_button.setEnabled(
            self.updater is not None and self.update_check_worker is None
        )

    @staticmethod
    def _format_megabytes(size_in_bytes: int) -> str:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"

    def _prepare_fill(self) -> None:
        issues = self.service.validate_day(self.blocks)
        if issues:
            QMessageBox.warning(
                self, "Validierung", "\n".join(issue.message for issue in issues)
            )
            return

        self.pending_steps = build_steps_for_blocks(
            self.blocks,
            include_lunch_expenses=self.lunch_expenses_checkbox.isChecked(),
        )
        message = (
            "Bitte jetzt das erste leere Auftragsfeld in Messerli anklicken.\n\n"
            "Nach dem Bestätigen startet ein 3-Sekunden-Countdown. ESC bricht sofort ab."
        )
        confirmed, target_window = self._confirm_fill_target(message)
        if not confirmed:
            return

        self.countdown_remaining = max(1, self.preferences.countdown_seconds)
        self.fill_button.setEnabled(False)
        self.lunch_expenses_checkbox.setEnabled(False)
        self._set_status(f"Countdown läuft: {self.countdown_remaining}")
        self.countdown_timer.start(1000)
        if target_window is not None:
            QTimer.singleShot(50, lambda: self._restore_external_window(target_window))

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

    def _scroll_timeline_to_default_hour(self) -> None:
        target_minutes = TIMELINE_DEFAULT_VISIBLE_HOUR * 60
        target_y = self.timeline.y_position_for_minutes(target_minutes)
        self.timeline_scroll.verticalScrollBar().setValue(
            max(0, target_y - self.timeline.top_padding)
        )

    def _confirm_fill_target(self, message: str) -> tuple[bool, int | None]:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Ausfüllen vorbereiten")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        dialog.setDefaultButton(QMessageBox.Ok)

        tracked_window: dict[str, int | None] = {"handle": None}
        tracker = QTimer(dialog)
        tracker.setInterval(150)

        def capture_external_window() -> None:
            window_handle = get_foreground_window_handle()
            if window_handle is None or is_current_process_window(window_handle):
                return
            tracked_window["handle"] = window_handle

        tracker.timeout.connect(capture_external_window)
        dialog.finished.connect(tracker.stop)
        tracker.start()

        confirmed = dialog.exec() == QMessageBox.Ok
        return confirmed, tracked_window["handle"]

    def _restore_external_window(self, window_handle: int) -> None:
        if activate_window(window_handle):
            logger.info("Restored focus to external window %s", window_handle)
            return
        logger.info("Could not restore focus to external window %s", window_handle)

    def _remember_preferences(self, block: TimeBlock) -> None:
        if block.block_type == "work":
            self.preferences.last_project_number = block.project_number
            self.preferences.last_work_remark = block.remark

    def _copy_current_day(self) -> None:
        if not self.blocks:
            QMessageBox.information(
                self,
                "Diesen Tag kopieren",
                "Für diesen Tag wurden keine Einträge gefunden.",
            )
            return
        self._copied_day_blocks = self._clone_blocks_for_date(
            self.blocks,
            self.current_date,
        )
        self._copied_day_source_date = self.current_date
        self._update_copy_paste_actions()
        self._set_day_action_status(
            f"{len(self._copied_day_blocks)} Einträge von "
            f"{self._format_day_label(self.current_date)} kopiert"
        )

    def _paste_copied_day(self) -> None:
        if not self._copied_day_blocks:
            return
        if not self._confirm_day_overwrite("Einfügen"):
            return
        self._replace_current_day_blocks(self._copied_day_blocks)
        source_label = (
            self._format_day_label(self._copied_day_source_date)
            if self._copied_day_source_date
            else "Zwischenablage"
        )
        self._set_day_action_status(f"Einträge von {source_label} eingefügt")

    def _paste_previous_day(self) -> None:
        current = date.fromisoformat(self.current_date)
        previous = (current - timedelta(days=1)).isoformat()
        previous_blocks = self.service.load_day(previous)
        if not previous_blocks:
            QMessageBox.information(
                self,
                "Vortag einfügen",
                "Für den Vortag wurden keine Einträge gefunden.",
            )
            return
        if not self._confirm_day_overwrite("Vortag einfügen"):
            return
        self._replace_current_day_blocks(previous_blocks)
        self._set_day_action_status("Vortag eingefügt")

    def _update_copy_paste_actions(self) -> None:
        self.paste_day_action.setEnabled(bool(self._copied_day_blocks))

    def _confirm_day_overwrite(self, title: str) -> bool:
        if not self.blocks:
            return True
        return (
            QMessageBox.question(
                self,
                title,
                "Dieser Tag enthält bereits Einträge und wird überschrieben.",
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            == QMessageBox.Ok
        )

    def _replace_current_day_blocks(self, source_blocks: list[TimeBlock]) -> None:
        self.blocks = self._clone_blocks_for_date(source_blocks, self.current_date)
        self._persist_current_day()
        self._refresh_lists()

    def _clone_blocks_for_date(
        self, source_blocks: list[TimeBlock], target_date: str
    ) -> list[TimeBlock]:
        return [
            TimeBlock(
                date=target_date,
                start_time=block.start_time,
                end_time=block.end_time,
                block_type=block.block_type,
                project_number=block.project_number,
                remark=block.remark,
            )
            for block in source_blocks
        ]

    def _format_day_label(self, day: str) -> str:
        qdate = QDate.fromString(day, "yyyy-MM-dd")
        if qdate.isValid():
            return qdate.toString("dd.MM.yyyy")
        return day

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

    def _position_day_action_status(self) -> None:
        if not self.day_action_status_label.isVisible():
            return
        button_bottom_right = self.copy_paste_button.mapTo(
            self,
            self.copy_paste_button.rect().bottomRight(),
        )
        x = button_bottom_right.x() - self.day_action_status_label.width()
        x = max(
            12,
            min(
                x,
                self.width() - self.day_action_status_label.width() - 12,
            ),
        )
        y = button_bottom_right.y() + 6
        self.day_action_status_label.move(x, y)

    def _position_lunch_expenses_notice(self) -> None:
        if not self.lunch_expenses_notice_label.isVisible():
            return
        checkbox_bottom_left = self.lunch_expenses_checkbox.mapTo(
            self,
            self.lunch_expenses_checkbox.rect().bottomLeft(),
        )
        checkbox_top_left = self.lunch_expenses_checkbox.mapTo(
            self,
            self.lunch_expenses_checkbox.rect().topLeft(),
        )
        x = max(
            12,
            min(
                checkbox_bottom_left.x(),
                self.width() - self.lunch_expenses_notice_label.width() - 12,
            ),
        )
        y = checkbox_bottom_left.y() + 8
        if y + self.lunch_expenses_notice_label.height() > self.height() - 12:
            y = checkbox_top_left.y() - self.lunch_expenses_notice_label.height() - 8
        y = max(12, y)
        self.lunch_expenses_notice_label.move(x, y)

    def _set_day_action_status(self, message: str) -> None:
        self.day_action_status_label.setText(message)
        self.day_action_status_label.adjustSize()
        self.day_action_status_label.setVisible(bool(message))
        if message:
            self._position_day_action_status()
            self.day_action_status_label.raise_()
            self.day_action_status_timer.start(3500)
        else:
            self.day_action_status_timer.stop()

    def _set_lunch_expenses_notice(self, message: str) -> None:
        self.lunch_expenses_notice_label.setText(message)
        self.lunch_expenses_notice_label.adjustSize()
        self.lunch_expenses_notice_label.setVisible(bool(message))
        if message:
            self._position_lunch_expenses_notice()
            self.lunch_expenses_notice_label.raise_()
            self.lunch_expenses_notice_timer.start(3500)
        else:
            self.lunch_expenses_notice_timer.stop()

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
