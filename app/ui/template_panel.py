from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.constants import MAX_FAVORITE_PROJECTS, WORK_REMARKS
from app.models.project_template import ProjectTemplate
from app.utils.paths import get_bundle_dir
from app.validation.validators import has_duplicate_project_number


class ProjectTemplatesWidget(QWidget):
    templates_changed = Signal(list)
    MAX_FAVORITES = MAX_FAVORITE_PROJECTS

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._templates: list[ProjectTemplate] = []
        self._selected_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QLabel("Projektvorlagen")
        header.setStyleSheet("font-weight: 700; font-size: 15px;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        self.list_widget.setSpacing(4)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget, stretch=1)

        self.form_group = QGroupBox("Vorlage bearbeiten")
        form_layout = QFormLayout(self.form_group)

        self.project_number_edit = QLineEdit()
        self.project_number_edit.setPlaceholderText("z.B. 25344")
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("Optionale Bezeichnung")
        self.default_remark_combo = QComboBox()
        self.default_remark_combo.addItem("")
        self.default_remark_combo.addItems(WORK_REMARKS)
        self.favorite_checkbox = QCheckBox("Im Zeitblock-Dialog als Favorit anzeigen")
        self.favorite_checkbox.setToolTip(
            "Favoriten erscheinen im Dialog als Schnellwahl-Buttons."
        )
        checked_icon = (
            get_bundle_dir() / "app" / "ui" / "assets" / "checkbox_checked.svg"
        ).as_posix()
        self.favorite_checkbox.setStyleSheet(
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

        form_layout.addRow("Projektnummer", self.project_number_edit)
        form_layout.addRow("Bezeichnung", self.display_name_edit)
        form_layout.addRow("Standardbemerkung", self.default_remark_combo)
        form_layout.addRow("Favorit", self.favorite_checkbox)
        layout.addWidget(self.form_group)

        button_row = QHBoxLayout()
        self.new_button = QPushButton("Neu")
        self.save_button = QPushButton("Speichern")
        self.delete_button = QPushButton("Löschen")
        button_row.addWidget(self.new_button)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.delete_button)
        layout.addLayout(button_row)

        self.new_button.clicked.connect(self._clear_form)
        self.save_button.clicked.connect(self._save_template)
        self.delete_button.clicked.connect(self._delete_template)

    def set_templates(self, templates: list[ProjectTemplate]) -> None:
        self._templates = [
            ProjectTemplate.from_dict(item.to_dict()) for item in templates
        ]
        self._templates.sort(
            key=lambda item: (
                not item.is_favorite,
                item.project_number,
                item.display_name,
                item.id,
            )
        )
        self._rebuild_list()
        self._clear_form()

    def templates(self) -> list[ProjectTemplate]:
        return [ProjectTemplate.from_dict(item.to_dict()) for item in self._templates]

    def _rebuild_list(self) -> None:
        self.list_widget.clear()
        for template in self._templates:
            item = QListWidgetItem()
            item.setData(256, template.id)
            self.list_widget.addItem(item)
            widget = self._build_template_item_widget(template)
            item.setSizeHint(QSize(0, max(widget.sizeHint().height(), 30)))
            self.list_widget.setItemWidget(item, widget)
        self._update_list_item_styles()

    def _clear_form(self) -> None:
        self._selected_id = None
        self.list_widget.clearSelection()
        self.project_number_edit.clear()
        self.display_name_edit.clear()
        self.default_remark_combo.setCurrentIndex(0)
        self.favorite_checkbox.setChecked(False)
        self._update_list_item_styles()
        self.project_number_edit.setFocus()

    def _on_selection_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self._selected_id = None
            self._update_list_item_styles()
            return
        template_id = current.data(256)
        template = self._find_template(template_id)
        if template is None:
            self._update_list_item_styles()
            return
        self._selected_id = template.id
        self.project_number_edit.setText(template.project_number)
        self.display_name_edit.setText(template.display_name)
        index = self.default_remark_combo.findText(template.default_remark)
        self.default_remark_combo.setCurrentIndex(max(index, 0))
        self.favorite_checkbox.setChecked(template.is_favorite)
        self._update_list_item_styles()

    def _save_template(self) -> None:
        project_number = self.project_number_edit.text().strip()
        if not project_number:
            QMessageBox.warning(self, "Vorlage", "Bitte eine Projektnummer angeben.")
            return
        if has_duplicate_project_number(
            self._templates, project_number, exclude_id=self._selected_id
        ):
            QMessageBox.warning(
                self,
                "Vorlage",
                "Diese Projektnummer existiert bereits und kann nicht doppelt gespeichert werden.",
            )
            return

        is_favorite = self.favorite_checkbox.isChecked()
        if is_favorite and self._favorite_count_excluding_selected() >= self.MAX_FAVORITES:
            QMessageBox.warning(
                self,
                "Vorlage",
                f"Es können maximal {self.MAX_FAVORITES} Favoriten gespeichert werden.",
            )
            return

        template = ProjectTemplate(
            id=self._selected_id or "",
            project_number=project_number,
            display_name=self.display_name_edit.text().strip(),
            default_remark=self.default_remark_combo.currentText().strip(),
            is_favorite=is_favorite,
        )
        if not template.id:
            template = ProjectTemplate.from_dict(template.to_dict())

        existing_index = next(
            (
                index
                for index, item in enumerate(self._templates)
                if item.id == template.id
            ),
            None,
        )
        if existing_index is None:
            self._templates.append(template)
        else:
            self._templates[existing_index] = template

        self._templates.sort(
            key=lambda item: (
                not item.is_favorite,
                item.project_number,
                item.display_name,
                item.id,
            )
        )
        self._rebuild_list()
        self.templates_changed.emit(self.templates())
        self._select_template(template.id)

    def _delete_template(self) -> None:
        if not self._selected_id:
            return
        self._templates = [
            item for item in self._templates if item.id != self._selected_id
        ]
        self._rebuild_list()
        self.templates_changed.emit(self.templates())
        self._clear_form()

    def _select_template(self, template_id: str) -> None:
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(256) == template_id:
                self.list_widget.setCurrentItem(item)
                break

    def _find_template(self, template_id: str | None) -> ProjectTemplate | None:
        if not template_id:
            return None
        return next((item for item in self._templates if item.id == template_id), None)

    def _favorite_count_excluding_selected(self) -> int:
        return sum(
            1
            for item in self._templates
            if item.is_favorite and item.id != self._selected_id
        )

    def _build_template_item_widget(self, template: ProjectTemplate) -> QWidget:
        widget = QWidget()
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        widget.setMinimumHeight(30)
        widget.setObjectName("TemplateListItem")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        title_label = QLabel(template.display_label())
        title_label.setObjectName("TemplateListTitle")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_label.setWordWrap(False)
        title_label.setStyleSheet("font-weight: 500; color: #0F172A;")
        layout.addWidget(title_label, stretch=1)

        if template.is_favorite:
            layout.addWidget(self._create_info_tag("Favorit", accent=True))

        layout.addStretch()
        return widget

    def _update_list_item_styles(self) -> None:
        current_item = self.list_widget.currentItem()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            widget = self.list_widget.itemWidget(item)
            if widget is None:
                continue
            self._set_template_item_selected(widget, item == current_item)

    def _set_template_item_selected(self, widget: QWidget, selected: bool) -> None:
        if selected:
            widget.setStyleSheet(
                """
                QWidget#TemplateListItem {
                    background: #DBEAFE;
                    border: 1px solid #93C5FD;
                    border-radius: 8px;
                }
                QLabel#TemplateListTitle {
                    color: #0F172A;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }
                """
            )
            return
        widget.setStyleSheet(
            """
            QWidget#TemplateListItem {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
            }
            QLabel#TemplateListTitle {
                color: #0F172A;
                font-weight: 500;
                background: transparent;
                border: none;
            }
            """
        )

    def _create_info_tag(self, text: str, accent: bool = False) -> QLabel:
        tag = QLabel(text)
        if accent:
            tag.setStyleSheet(
                "background: #DBEAFE; color: #1D4ED8; border: 1px solid #93C5FD; "
                "border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
            )
        else:
            tag.setStyleSheet(
                "background: #E2E8F0; color: #334155; border: 1px solid #CBD5E1; "
                "border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
        return tag
