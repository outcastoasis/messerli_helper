from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __version__
from app.metadata import APP_NAME, APP_USER_MODEL_ID
from app.services.day_service import DayService
from app.services.update_service import GitHubReleaseUpdater
from app.storage.json_store import JsonStorage
from app.ui.main_window import MainWindow
from app.utils.logging_config import configure_logging
from app.utils.paths import get_bundle_dir, get_default_data_dir
from app.utils.windows import set_current_process_app_user_model_id


def main() -> int:
    data_dir = get_default_data_dir()
    bundle_dir = get_bundle_dir()
    icon_path = bundle_dir / "packaging" / "windows" / "app.ico"
    configure_logging(data_dir / "logs" / "messerli-helper.log")

    set_current_process_app_user_model_id(APP_USER_MODEL_ID)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    storage = JsonStorage(
        data_dir,
        seed_template_file=bundle_dir / "examples" / "project_templates.json",
    )
    service = DayService(storage)
    updater = GitHubReleaseUpdater()

    window = MainWindow(service, updater=updater)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
