from __future__ import annotations

from datetime import date
from PySide6.QtCore import QSignalBlocker, Qt, QTime
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.constants import (
    BLOCK_TYPE_BREAK,
    BLOCK_TYPE_COMPENSATION,
    BLOCK_TYPE_WORK,
    BREAK_REMARKS,
    COMPENSATION_REMARK,
    COMPENSATION_REMARKS,
    SLOT_MINUTES,
    WORK_REMARKS,
)
from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.utils.time_utils import parse_time_text
from app.utils.paths import get_bundle_dir


class QuarterHourTimeEdit(QTimeEdit):
    """Time edit with 15-minute stepping and snapping."""

    def stepBy(self, steps: int) -> None:  # noqa: N802 - Qt API
        updated = self.time().addSecs(steps * SLOT_MINUTES * 60)
        self.setTime(updated)

    def setTime(self, time: QTime) -> None:  # noqa: N802 - Qt API
        minute = time.minute()
        snapped_minute = round(minute / SLOT_MINUTES) * SLOT_MINUTES
        adjusted = time
        if snapped_minute == 60:
            adjusted = adjusted.addSecs(60 * 60)
            snapped_minute = 0
        adjusted = QTime(adjusted.hour(), snapped_minute)
        super().setTime(adjusted)


class BlockEditorDialog(QDialog):
    def __init__(
        self,
        block: TimeBlock,
        templates: list[ProjectTemplate],
        preferences: AppPreferences,
        is_new: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            "Zeitblock bearbeiten" if not is_new else "Zeitblock anlegen"
        )
        self.block = TimeBlock.from_dict(block.to_dict())
        self.templates = templates
        self.preferences = preferences
        self.is_new = is_new
        self.result_action = "save"
        self.result_block: TimeBlock | None = None
        self._remark_buttons: dict[str, QPushButton] = {}
        self._block_type_buttons: dict[str, QPushButton] = {}
        self._favorite_project_buttons: dict[str, QPushButton] = {}
        self._remark_sections: dict[str, list[QWidget]] = {
            BLOCK_TYPE_WORK: [],
            BLOCK_TYPE_BREAK: [],
            BLOCK_TYPE_COMPENSATION: [],
        }
        self._selected_remark = self.block.remark

        self._build_ui()
        self._load_initial_state()

    def _build_ui(self) -> None:
        self.setObjectName("BlockEditorDialog")
        self.setMinimumWidth(392)
        self.setStyleSheet(self._dialog_stylesheet())

        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SetFixedSize)
        main_layout.setContentsMargins(18, 14, 18, 12)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._create_divider())

        self.block_type_combo = QComboBox()
        self.block_type_combo.hide()
        self.block_type_combo.addItem("Normal", BLOCK_TYPE_WORK)
        self.block_type_combo.addItem("Pause", BLOCK_TYPE_BREAK)
        self.block_type_combo.addItem("Kompensation", BLOCK_TYPE_COMPENSATION)
        main_layout.addWidget(self.block_type_combo)

        main_layout.addWidget(self._create_section_label("Typ"))
        main_layout.addWidget(self._build_type_selector())

        self.project_section_label = self._create_section_label("Projekt")
        self.project_section_widget = self._build_project_section()
        main_layout.addWidget(self.project_section_label)
        main_layout.addWidget(self.project_section_widget)

        main_layout.addWidget(self._create_section_label("Zeitraum"))
        main_layout.addWidget(self._build_time_section())

        main_layout.addWidget(self._create_divider())

        main_layout.addWidget(self._create_section_label("Bemerkung"))
        remarks_widget = self._build_remark_section()
        main_layout.addWidget(remarks_widget)

        if not self.is_new:
            main_layout.addWidget(self._create_divider())
            main_layout.addLayout(self._build_extra_actions())

        main_layout.addWidget(self._create_divider())
        main_layout.addLayout(self._build_footer())

        self.project_combo.activated.connect(self._apply_template_selection)
        self.project_combo.editTextChanged.connect(self._update_project_button_state)
        self.block_type_combo.currentIndexChanged.connect(self._update_ui_for_type)
        self.start_edit.timeChanged.connect(self._update_duration_badge)
        self.end_edit.timeChanged.connect(self._update_duration_badge)

    def _load_initial_state(self) -> None:
        if self.block.project_number:
            self.project_combo.setEditText(self.block.project_number)
        elif self.preferences.last_project_number:
            self.project_combo.setEditText(self.preferences.last_project_number)

        initial_type = (
            self.block.block_type
            if self.block.block_type
            in {BLOCK_TYPE_WORK, BLOCK_TYPE_BREAK, BLOCK_TYPE_COMPENSATION}
            else BLOCK_TYPE_WORK
        )
        self.block_type_combo.setCurrentIndex(
            self.block_type_combo.findData(initial_type)
        )
        if (
            not self._selected_remark
            and self.preferences.last_work_remark
            and initial_type == BLOCK_TYPE_WORK
        ):
            self._selected_remark = self.preferences.last_work_remark

        self._update_ui_for_type()
        self._update_duration_badge()
        if self._selected_remark:
            self._select_remark(self._selected_remark)
        self.adjustSize()

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel("Zeitblock erfassen" if self.is_new else "Zeitblock bearbeiten")
        title.setObjectName("DialogTitle")
        subtitle = QLabel(self._format_date_label(self.block.date))
        subtitle.setObjectName("DialogSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_type_selector(self) -> QWidget:
        container = QWidget()
        container.setObjectName("SegmentedContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for label, value in (
            ("Normal", BLOCK_TYPE_WORK),
            ("Pause", BLOCK_TYPE_BREAK),
            ("Kompensation", BLOCK_TYPE_COMPENSATION),
        ):
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(
                lambda checked=False, block_type=value: self._set_block_type(block_type)
            )
            self._block_type_buttons[value] = button
            layout.addWidget(button)
        return container

    def _build_project_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.project_combo = QComboBox()
        self.project_combo.setObjectName("ProjectCombo")
        self.project_combo.setEditable(True)
        self.project_combo.setInsertPolicy(QComboBox.NoInsert)
        self.project_combo.addItem("")
        for template in self.templates:
            self.project_combo.addItem(template.display_label(), template.id)
        layout.addWidget(self.project_combo)

        self.favorite_caption_label = QLabel("Schnellauswahl (Favoriten)")
        self.favorite_caption_label.setObjectName("CaptionLabel")
        layout.addWidget(self.favorite_caption_label)

        self.favorite_projects_widget = QWidget()
        favorite_layout = QHBoxLayout(self.favorite_projects_widget)
        favorite_layout.setContentsMargins(0, 0, 0, 0)
        favorite_layout.setSpacing(8)
        for template in self._favorite_templates():
            button = QPushButton(template.project_number)
            button.setObjectName("ChipButton")
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.setMinimumWidth(
                max(
                    64,
                    button.fontMetrics().horizontalAdvance(template.project_number)
                    + 24,
                )
            )
            if template.display_name:
                button.setToolTip(template.display_label())
            button.clicked.connect(
                lambda checked=False, template_id=template.id: self._apply_template_by_id(
                    template_id
                )
            )
            self._favorite_project_buttons[template.id] = button
            favorite_layout.addWidget(button, alignment=Qt.AlignLeft)
        favorite_layout.addStretch()
        layout.addWidget(self.favorite_projects_widget)
        return container

    def _build_time_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        labels_row = QHBoxLayout()
        labels_row.setContentsMargins(0, 0, 0, 0)
        labels_row.setSpacing(8)
        labels_row.addWidget(self._create_field_caption("Von"), 1)
        spacer = QLabel("")
        spacer.setFixedWidth(20)
        labels_row.addWidget(spacer)
        labels_row.addWidget(self._create_field_caption("Bis"), 1)
        layout.addLayout(labels_row)

        self.start_edit = QuarterHourTimeEdit()
        self.end_edit = QuarterHourTimeEdit()
        for edit, value in (
            (self.start_edit, self.block.start_time),
            (self.end_edit, self.block.end_time),
        ):
            edit.setDisplayFormat("HH:mm")
            edit.setObjectName("TimeEdit")
            edit.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
            edit.setAccelerated(True)
            edit.setFixedSize(124, 34)
            edit.setTime(self._to_qtime(value))

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(10)
        time_row.addWidget(self.start_edit, 1)

        arrow = QLabel("→")
        arrow.setObjectName("ArrowLabel")
        arrow.setAlignment(Qt.AlignCenter)
        time_row.addWidget(arrow)

        time_row.addWidget(self.end_edit, 1)
        layout.addLayout(time_row)

        self.duration_badge = QLabel("")
        self.duration_badge.setObjectName("DurationBadge")
        self.duration_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        layout.addWidget(self.duration_badge, alignment=Qt.AlignLeft)

        return container

    def _build_remark_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._add_remark_group(
            layout,
            BLOCK_TYPE_WORK,
            "Allgemein",
            WORK_REMARKS[:4],
            columns=4,
        )
        self._add_remark_group(
            layout,
            BLOCK_TYPE_WORK,
            "Sys",
            WORK_REMARKS[4:7],
            columns=3,
        )
        self._add_remark_group(
            layout,
            BLOCK_TYPE_WORK,
            "Event",
            WORK_REMARKS[7:10],
            columns=3,
        )
        self._add_remark_group(
            layout,
            BLOCK_TYPE_BREAK,
            "Pause",
            BREAK_REMARKS,
            columns=2,
        )
        self._add_remark_group(
            layout,
            BLOCK_TYPE_COMPENSATION,
            "Kompensation",
            COMPENSATION_REMARKS,
            columns=1,
        )

        return container

    def _add_remark_group(
        self,
        parent_layout: QVBoxLayout,
        block_type: str,
        title: str,
        remarks: list[str],
        columns: int,
    ) -> None:
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        label = QLabel(title.upper())
        label.setObjectName("GroupLabel")
        section_layout.addWidget(label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index, remark in enumerate(remarks):
            button = QPushButton(self._remark_button_text(remark))
            button.setObjectName("RemarkButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, value=remark: self._select_remark(value)
            )
            self._remark_buttons[remark] = button
            grid.addWidget(button, index // columns, index % columns)

        section_layout.addLayout(grid)
        parent_layout.addWidget(section)
        self._remark_sections[block_type].append(section)

    def _build_extra_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        split_button = QPushButton("Block teilen")
        split_button.setObjectName("SecondaryActionButton")
        split_button.clicked.connect(self._split)
        split_button.setFixedWidth(84)
        layout.addWidget(split_button)

        delete_button = QPushButton("Löschen")
        delete_button.setObjectName("DangerActionButton")
        delete_button.clicked.connect(self._delete)
        delete_button.setFixedWidth(74)
        layout.addWidget(delete_button)

        layout.addStretch()
        return layout

    def _build_footer(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        cancel_button = QPushButton("Abbrechen")
        cancel_button.setObjectName("FooterGhostButton")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setFixedWidth(82)

        save_button = QPushButton("Speichern")
        save_button.setObjectName("FooterPrimaryButton")
        save_button.setDefault(True)
        save_button.clicked.connect(self._save)
        save_button.setFixedWidth(122)

        layout.addWidget(cancel_button)
        layout.addStretch()
        layout.addWidget(save_button)
        return layout

    def _apply_template_selection(self, index: int) -> None:
        template_id = self.project_combo.itemData(index)
        self._apply_template_by_id(template_id)

    def _apply_template_by_id(self, template_id: str | None) -> None:
        template = next(
            (item for item in self.templates if item.id == template_id), None
        )
        if template is None:
            return
        self.project_combo.setEditText(template.project_number)
        self._update_project_button_state(template.project_number)
        if (
            self.block_type_combo.currentData() == BLOCK_TYPE_WORK
            and template.default_remark
        ):
            self._select_remark(template.default_remark)

    def _update_ui_for_type(self) -> None:
        block_type = self.block_type_combo.currentData()
        self._update_block_type_button_state()

        is_work_type = block_type == BLOCK_TYPE_WORK
        self.project_section_label.setVisible(is_work_type)
        self.project_section_widget.setVisible(is_work_type)
        self.project_combo.setEnabled(is_work_type)
        self.favorite_caption_label.setVisible(
            is_work_type and bool(self._favorite_project_buttons)
        )
        self.favorite_projects_widget.setVisible(
            is_work_type and bool(self._favorite_project_buttons)
        )
        for button in self._favorite_project_buttons.values():
            button.setEnabled(is_work_type)

        if not is_work_type:
            self.project_combo.setEditText("")

        for item_type, sections in self._remark_sections.items():
            for section in sections:
                section.setVisible(item_type == block_type)

        allowed_remarks = self._allowed_remarks_for_type(block_type)
        for remark, button in self._remark_buttons.items():
            if remark not in allowed_remarks:
                button.setChecked(False)

        if self._selected_remark not in allowed_remarks:
            self._selected_remark = self._default_remark_for_type(block_type)
        if self._selected_remark:
            self._select_remark(self._selected_remark)

        self._update_project_button_state(self.project_combo.currentText())
        self.layout().activate()
        self.adjustSize()

    def _select_remark(self, remark: str) -> None:
        if remark not in self._remark_buttons:
            return
        self._selected_remark = remark
        for candidate, button in self._remark_buttons.items():
            button.setChecked(candidate == remark)

    def _set_block_type(self, block_type: str) -> None:
        index = self.block_type_combo.findData(block_type)
        if index >= 0:
            self.block_type_combo.setCurrentIndex(index)

    def _update_block_type_button_state(self) -> None:
        current_type = self.block_type_combo.currentData()
        for block_type, button in self._block_type_buttons.items():
            button.setChecked(block_type == current_type)

    def _update_project_button_state(self, project_number: str) -> None:
        is_work_type = self.block_type_combo.currentData() == BLOCK_TYPE_WORK
        normalized = project_number.strip()
        for template in self._favorite_templates():
            button = self._favorite_project_buttons.get(template.id)
            if button is None:
                continue
            button.setChecked(is_work_type and template.project_number == normalized)

    def _update_duration_badge(self) -> None:
        start_minutes = parse_time_text(self.start_edit.time().toString("HH:mm"))
        end_minutes = parse_time_text(self.end_edit.time().toString("HH:mm"))
        difference = end_minutes - start_minutes

        if difference <= 0:
            self.duration_badge.setObjectName("DurationBadgeInvalid")
            self.duration_badge.setText("Ungueltiger Zeitraum")
        else:
            self.duration_badge.setObjectName("DurationBadge")
            self.duration_badge.setText(self._format_duration_text(difference))
        self.duration_badge.style().unpolish(self.duration_badge)
        self.duration_badge.style().polish(self.duration_badge)

    def _save(self) -> None:
        try:
            block = self._build_block()
        except ValueError as exc:
            QMessageBox.warning(self, "Zeitblock", str(exc))
            return
        self.result_action = "save"
        self.result_block = block
        self.accept()

    def _split(self) -> None:
        try:
            block = self._build_block()
        except ValueError as exc:
            QMessageBox.warning(self, "Zeitblock", str(exc))
            return
        if parse_time_text(block.end_time) - parse_time_text(block.start_time) < 30:
            QMessageBox.warning(
                self, "Zeitblock", "Der Block muss mindestens 30 Minuten lang sein."
            )
            return
        self.result_action = "split"
        self.result_block = block
        self.accept()

    def _delete(self) -> None:
        self.result_action = "delete"
        self.result_block = self.block
        self.accept()

    def _build_block(self) -> TimeBlock:
        block_type = self.block_type_combo.currentData()
        start_time = self.start_edit.time().toString("HH:mm")
        end_time = self.end_edit.time().toString("HH:mm")
        project_number = (
            self.project_combo.currentText().strip()
            if block_type == BLOCK_TYPE_WORK
            else ""
        )

        if not self._selected_remark:
            raise ValueError("Bitte eine Bemerkung wählen.")
        if block_type == BLOCK_TYPE_WORK and not project_number:
            raise ValueError("Bitte eine Projektnummer angeben.")

        block = TimeBlock(
            id=self.block.id,
            date=self.block.date,
            start_time=start_time,
            end_time=end_time,
            block_type=block_type,
            project_number=project_number,
            remark=self._selected_remark,
        )

        if parse_time_text(block.start_time) >= parse_time_text(block.end_time):
            raise ValueError("Startzeit muss vor Endzeit liegen.")

        return block

    @staticmethod
    def _allowed_remarks_for_type(block_type: str) -> list[str]:
        if block_type == BLOCK_TYPE_WORK:
            return WORK_REMARKS
        if block_type == BLOCK_TYPE_BREAK:
            return BREAK_REMARKS
        if block_type == BLOCK_TYPE_COMPENSATION:
            return COMPENSATION_REMARKS
        return []

    @staticmethod
    def _default_remark_for_type(block_type: str) -> str:
        if block_type == BLOCK_TYPE_COMPENSATION:
            return COMPENSATION_REMARK
        return ""

    def _favorite_templates(self) -> list[ProjectTemplate]:
        return sorted(
            (template for template in self.templates if template.is_favorite),
            key=lambda item: (item.project_number, item.display_name, item.id),
        )[:3]

    @staticmethod
    def _to_qtime(value: str) -> QTime:
        hour, minute = (int(part) for part in value.split(":"))
        return QTime(hour, minute)

    @staticmethod
    def _create_section_label(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("SectionLabel")
        return label

    @staticmethod
    def _create_field_caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldCaption")
        return label

    @staticmethod
    def _create_divider() -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("SectionDivider")
        return divider

    @staticmethod
    def _remark_button_text(remark: str) -> str:
        if remark.startswith("Sys. "):
            return remark.replace("Sys. ", "", 1)
        if remark.startswith("Event "):
            return remark.replace("Event ", "", 1)
        return remark

    @staticmethod
    def _format_duration_text(total_minutes: int) -> str:
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours} Std. {minutes:02d} Min."

    @staticmethod
    def _format_date_label(value: str) -> str:
        weekdays = [
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        ]
        months = [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ]
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return value
        return (
            f"{weekdays[parsed.weekday()]}, "
            f"{parsed.day}. {months[parsed.month - 1]} {parsed.year}"
        )

    @staticmethod
    def _dialog_stylesheet() -> str:
        assets_dir = get_bundle_dir() / "app" / "ui" / "assets"
        combo_arrow_icon = (assets_dir / "dropdown_chevron.svg").as_posix()
        spinner_up_icon = (assets_dir / "spinner_up.svg").as_posix()
        spinner_down_icon = (assets_dir / "spinner_down.svg").as_posix()
        return """
        QDialog#BlockEditorDialog {
            background: #F7F4EE;
            color: #2E2A25;
            border-radius: 22px;
        }
        QLabel#DialogTitle {
            font-size: 20px;
            font-weight: 700;
            color: #2C2823;
        }
        QLabel#DialogSubtitle {
            font-size: 12px;
            color: #8A8279;
        }
        QLabel#SectionLabel {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            color: #A09990;
            text-transform: uppercase;
        }
        QLabel#CaptionLabel,
        QLabel#FieldCaption,
        QLabel#GroupLabel {
            font-size: 11px;
            font-weight: 600;
            color: #9B948A;
        }
        QLabel#ArrowLabel {
            font-size: 16px;
            color: #9C9388;
            min-width: 18px;
        }
        QFrame#SectionDivider {
            color: #DDD4C9;
            background: #DDD4C9;
            max-height: 1px;
            border: none;
        }
        QWidget#SegmentedContainer {
            background: #EDE6DC;
            border-radius: 12px;
        }
        QPushButton#SegmentButton {
            border: none;
            border-radius: 10px;
            min-height: 30px;
            padding: 6px 10px;
            background: transparent;
            color: #6D655C;
            font-weight: 600;
        }
        QPushButton#SegmentButton:checked {
            background: #FFFFFF;
            color: #2C2823;
            border: 1px solid #D9CFC1;
        }
        QComboBox#ProjectCombo {
            min-height: 32px;
            border: 1px solid #CFC5B8;
            border-radius: 10px;
            padding: 5px 12px;
            background: #FFFCF7;
            color: #2C2823;
            selection-background-color: #DDE6FF;
        }
        QComboBox#ProjectCombo::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 34px;
            border: none;
            background: transparent;
        }
        QComboBox#ProjectCombo::down-arrow {
            image: url("%s");
            width: 12px;
            height: 8px;
        }
        QComboBox#ProjectCombo QAbstractItemView {
            border: 1px solid #D8CEC1;
            background: #FFFCF7;
            selection-background-color: #E8EEFF;
            selection-color: #2C2823;
        }
        QTimeEdit#TimeEdit {
            border: 1px solid #CFC5B8;
            border-radius: 10px;
            padding: 4px 40px 4px 12px;
            background: #FFFCF7;
            color: #2C2823;
            selection-background-color: #DDE6FF;
        }
        QTimeEdit#TimeEdit::up-button,
        QTimeEdit#TimeEdit::down-button {
            subcontrol-origin: border;
            width: 18px;
            border: none;
            background: transparent;
        }
        QTimeEdit#TimeEdit::up-button {
            subcontrol-position: top right;
            right: 20px;
            top: 4px;
        }
        QTimeEdit#TimeEdit::down-button {
            subcontrol-position: bottom right;
            right: 20px;
            bottom: 4px;
        }
        QTimeEdit#TimeEdit::up-arrow,
        QTimeEdit#TimeEdit::down-arrow {
            width: 8px;
            height: 8px;
        }
        QTimeEdit#TimeEdit::up-arrow {
            image: url("%s");
        }
        QTimeEdit#TimeEdit::down-arrow {
            image: url("%s");
        }
        QPushButton#ChipButton,
        QPushButton#RemarkButton {
            border: 1px solid #CEC4B7;
            border-radius: 16px;
            min-height: 30px;
            padding: 6px 12px;
            background: #FBF8F3;
            color: #6C645B;
            font-weight: 500;
        }
        QPushButton#ChipButton:hover,
        QPushButton#RemarkButton:hover {
            border-color: #BFB3A3;
            background: #FFFFFF;
        }
        QPushButton#ChipButton:checked,
        QPushButton#RemarkButton:checked {
            background: #E8EEFF;
            border-color: #94AFFF;
            color: #3452D1;
            font-weight: 600;
        }
        QLabel#DurationBadge,
        QLabel#DurationBadgeInvalid {
            padding: 5px 10px;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 600;
        }
        QLabel#DurationBadge {
            color: #2E7D4F;
            background: #EDF9EF;
            border: 1px solid #C9E9CF;
        }
        QLabel#DurationBadgeInvalid {
            color: #B45309;
            background: #FFF4E5;
            border: 1px solid #F3D1A7;
        }
        QPushButton#SecondaryActionButton,
        QPushButton#DangerActionButton,
        QPushButton#FooterGhostButton,
        QPushButton#FooterPrimaryButton {
            min-height: 30px;
            border-radius: 10px;
            font-weight: 600;
            padding: 5px 10px;
        }
        QPushButton#SecondaryActionButton,
        QPushButton#FooterGhostButton {
            background: #F4EFE7;
            color: #645C54;
            border: 1px solid #D5CABE;
        }
        QPushButton#DangerActionButton {
            background: #FFF3F0;
            color: #B24D3A;
            border: 1px solid #E9C2BA;
        }
        QPushButton#FooterPrimaryButton {
            background: #4055D6;
            color: #FFFFFF;
            border: 1px solid #4055D6;
        }
        QPushButton#FooterPrimaryButton:hover {
            background: #3548C3;
            border-color: #3548C3;
        }
        """ % (
            combo_arrow_icon,
            spinner_up_icon,
            spinner_down_icon,
        )
