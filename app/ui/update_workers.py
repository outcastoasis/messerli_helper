from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.update_service import AppUpdate, GitHubReleaseUpdater


class UpdateCheckWorker(QThread):
    completed = Signal(object, bool)

    def __init__(
        self,
        updater: GitHubReleaseUpdater,
        manual: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.updater = updater
        self.manual = manual

    def run(self) -> None:
        result = self.updater.check_for_updates()
        self.completed.emit(result, self.manual)


class UpdateDownloadWorker(QThread):
    progress_changed = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        updater: GitHubReleaseUpdater,
        update: AppUpdate,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.updater = updater
        self.update = update

    def run(self) -> None:
        try:
            installer_path = self.updater.download_update(
                self.update,
                progress_callback=self.progress_changed.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(str(Path(installer_path)))
