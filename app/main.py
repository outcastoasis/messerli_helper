from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __version__
from app.metadata import APP_NAME, APP_USER_MODEL_ID
from app.startup import (
    SingleInstanceCoordinator,
    build_single_instance_key,
    create_startup_splash,
    update_startup_message,
)
from app.utils.paths import get_bundle_dir
from app.utils.startup_profile import StartupProfiler, get_auto_exit_delay_ms
from app.utils.windows import set_current_process_app_user_model_id

try:
    import pyi_splash
except ImportError:  # pragma: no cover - available only in frozen builds with boot splash
    pyi_splash = None


def _update_bootloader_splash(message: str) -> None:
    if pyi_splash is None or not pyi_splash.is_alive():
        return
    try:
        pyi_splash.update_text(message)
    except Exception:
        pass


def _close_bootloader_splash() -> None:
    if pyi_splash is None or not pyi_splash.is_alive():
        return
    try:
        pyi_splash.close()
    except Exception:
        pass


def main() -> int:
    profiler = StartupProfiler()
    profiler.checkpoint(
        "main.enter",
        frozen=bool(getattr(sys, "frozen", False)),
        has_meipass=bool(getattr(sys, "_MEIPASS", None)),
    )

    bundle_dir = get_bundle_dir()
    icon_path = bundle_dir / "packaging" / "windows" / "app.ico"
    _update_bootloader_splash("Starte Anwendung...")
    profiler.checkpoint("bootloader_splash.updated")
    set_current_process_app_user_model_id(APP_USER_MODEL_ID)

    app = QApplication(sys.argv)
    profiler.checkpoint("qapplication.created")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if icon_path.exists():
        app.setWindowIcon(icon)

    instance_coordinator = SingleInstanceCoordinator(
        build_single_instance_key(APP_USER_MODEL_ID),
        app,
    )
    if not instance_coordinator.ensure_primary():
        profiler.checkpoint("single_instance.forwarded_to_running_app")
        _close_bootloader_splash()
        return 0
    profiler.checkpoint("single_instance.primary_ready")

    splash = create_startup_splash(
        APP_NAME,
        __version__,
        icon if not icon.isNull() else None,
    )
    splash.show()
    app.processEvents()
    profiler.checkpoint("qt_splash.visible")
    _close_bootloader_splash()

    update_startup_message(splash, "Initialisiere Anwendung...")
    app.processEvents()
    profiler.checkpoint("startup_message.initializing")

    from app.services.day_service import DayService
    from app.services.update_service import GitHubReleaseUpdater
    from app.storage.json_store import JsonStorage
    from app.ui.main_window import MainWindow
    from app.utils.logging_config import configure_logging
    from app.utils.paths import get_default_data_dir

    profiler.checkpoint("startup_imports.loaded")

    data_dir = get_default_data_dir()
    configure_logging(data_dir / "logs" / "messerli-helper.log")
    profiler.checkpoint("logging.configured", data_dir=str(data_dir))

    update_startup_message(splash, "Lade gespeicherte Daten...")
    app.processEvents()
    storage = JsonStorage(
        data_dir,
        seed_template_file=bundle_dir / "examples" / "project_templates.json",
    )
    service = DayService(storage)
    profiler.checkpoint("storage_and_service.ready")

    update_startup_message(splash, "Prüfe Update-Dienst und Fenster...")
    app.processEvents()
    updater = GitHubReleaseUpdater()
    profiler.checkpoint("updater.ready")

    window = MainWindow(service, updater=updater)
    profiler.checkpoint("main_window.created")
    instance_coordinator.set_activation_handler(window.bring_to_front)
    window.show()
    splash.finish(window)
    profiler.checkpoint("main_window.visible")

    auto_exit_delay_ms = get_auto_exit_delay_ms()
    if auto_exit_delay_ms is not None:
        QTimer.singleShot(auto_exit_delay_ms, app.quit)
        profiler.checkpoint("auto_exit.scheduled", delay_ms=auto_exit_delay_ms)

    exit_code = app.exec()
    profiler.checkpoint("app.exec.finished", exit_code=exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
