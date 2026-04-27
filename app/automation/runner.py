from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

from app.automation.sequence import AutomationStep

logger = logging.getLogger(__name__)

try:
    import keyboard  # type: ignore
except ImportError:  # pragma: no cover - depends on local environment
    keyboard = None

try:
    import pyautogui  # type: ignore
except ImportError:  # pragma: no cover - depends on local environment
    pyautogui = None


class AutomationAborted(Exception):
    """Raised when the keyboard sequence was cancelled."""


class AutomationWorker(QThread):
    status_changed = Signal(str)
    completed = Signal(bool, str)

    def __init__(
        self, steps: list[AutomationStep], typing_interval: float = 0.12
    ) -> None:
        super().__init__()
        self.steps = steps
        self.typing_interval = typing_interval
        self._abort_requested = False

    def request_abort(self) -> None:
        self._abort_requested = True

    def run(self) -> None:  # noqa: D401 - Qt run method
        hotkey_handle = None
        try:
            if pyautogui is None:
                raise RuntimeError("pyautogui ist nicht installiert.")

            if keyboard is not None:
                hotkey_handle = keyboard.add_hotkey("esc", self.request_abort)

            self.status_changed.emit("Ausfüllen aktiv")
            logger.info("Automation started with %s steps", len(self.steps))

            for step in self.steps:
                self._ensure_not_aborted()
                logger.info("Automation step: %s %s", step.action, step.value)
                if step.action == "write":
                    pyautogui.write(
                        step.value, interval=max(self.typing_interval / 3, 0.03)
                    )
                elif step.action == "press":
                    pyautogui.press(step.value)
                elif step.action == "wait":
                    time.sleep(float(step.value))
                else:
                    raise RuntimeError(f"Unbekannter Automation-Schritt: {step.action}")
                time.sleep(self._post_step_delay(step))

            self.status_changed.emit("abgeschlossen")
            self.completed.emit(True, "abgeschlossen")
            logger.info("Automation finished successfully")
        except AutomationAborted:
            self.status_changed.emit("abgebrochen")
            self.completed.emit(False, "abgebrochen")
            logger.info("Automation aborted by user")
        except Exception as exc:  # pragma: no cover - UI worker path
            logger.exception("Automation failed")
            message = f"Fehler bei Eingabe: {exc}"
            self.status_changed.emit(message)
            self.completed.emit(False, message)
        finally:
            if keyboard is not None and hotkey_handle is not None:
                try:
                    keyboard.remove_hotkey(hotkey_handle)
                except KeyError:
                    pass

    def _ensure_not_aborted(self) -> None:
        if self._abort_requested:
            raise AutomationAborted
        if keyboard is not None and keyboard.is_pressed("esc"):
            raise AutomationAborted

    def _post_step_delay(self, step: AutomationStep) -> float:
        if step.action == "press" and step.value == "enter":
            # Messerli needs a little more time after focus-changing Enter steps.
            return max(self.typing_interval * 1.75, 0.22)
        if step.action == "write":
            return max(self.typing_interval, 0.12)
        if step.action == "wait":
            return 0
        return max(self.typing_interval, 0.1)
