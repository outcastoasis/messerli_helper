from __future__ import annotations

import logging
import re
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QSplashScreen

logger = logging.getLogger(__name__)

_ACTIVATE_MESSAGE = b"activate"


def build_single_instance_key(app_user_model_id: str) -> str:
    """Return a stable IPC key that can be used across launches."""
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", app_user_model_id.strip())
    return f"{normalized or 'messerli-helper'}-single-instance"


class SingleInstanceCoordinator(QObject):
    """Keep a single primary instance alive and forward focus requests."""

    def __init__(self, server_name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.server_name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._handle_new_connection)
        self._activation_handler: Callable[[], None] | None = None
        self._pending_activation = False

    def ensure_primary(self) -> bool:
        if self._notify_existing_instance():
            return False

        if self.server.listen(self.server_name):
            return True

        logger.warning(
            "Could not listen on startup IPC channel '%s': %s",
            self.server_name,
            self.server.errorString(),
        )

        # A stale local server can remain after a crash. Remove it and retry once.
        QLocalServer.removeServer(self.server_name)
        if self._notify_existing_instance():
            return False
        if self.server.listen(self.server_name):
            return True

        raise RuntimeError(
            f"Single-instance channel could not be created: {self.server.errorString()}"
        )

    def set_activation_handler(self, handler: Callable[[], None]) -> None:
        self._activation_handler = handler
        if not self._pending_activation:
            return
        self._pending_activation = False
        handler()

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(200):
            return False
        socket.write(_ACTIVATE_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        socket.waitForDisconnected(200)
        logger.info("Forwarded activation request to running instance")
        return True

    def _handle_new_connection(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                return
            socket.waitForReadyRead(200)
            payload = bytes(socket.readAll())
            socket.disconnectFromServer()
            socket.deleteLater()
            if payload and payload != _ACTIVATE_MESSAGE:
                continue
            if self._activation_handler is None:
                self._pending_activation = True
                continue
            self._activation_handler()


def create_startup_splash(
    app_name: str,
    version: str,
    icon: QIcon | None = None,
) -> QSplashScreen:
    pixmap = QPixmap(460, 240)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setBrush(QColor("#F4F0E8"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, 460, 240, 24, 24)

    painter.setBrush(QColor("#17324D"))
    painter.drawRoundedRect(0, 0, 460, 92, 24, 24)
    painter.drawRect(0, 46, 460, 46)

    painter.setPen(QColor("#F4F0E8"))
    painter.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
    painter.drawText(140, 54, app_name)

    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("#D8E3ED"))
    painter.drawText(140, 80, f"Version {version}")

    if icon is not None and not icon.isNull():
        icon_pixmap = icon.pixmap(72, 72)
        painter.drawPixmap(40, 24, icon_pixmap)

    painter.setPen(QColor("#17324D"))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(40, 150, "Die Anwendung wird vorbereitet...")

    painter.setPen(QColor("#49657F"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setWindowFlag(Qt.SplashScreen, True)
    splash.showMessage(
        "Starte Anwendung...",
        Qt.AlignHCenter | Qt.AlignBottom,
        QColor("#17324D"),
    )

    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        screen_geometry = screen.availableGeometry()
        target_geometry = splash.frameGeometry()
        target_geometry.moveCenter(screen_geometry.center())
        splash.move(target_geometry.topLeft())

    return splash


def update_startup_message(splash: QSplashScreen, message: str) -> None:
    splash.showMessage(message, Qt.AlignHCenter | Qt.AlignBottom, QColor("#17324D"))
    splash.repaint()
