from __future__ import annotations

import logging
import ctypes
import time
from ctypes import wintypes

from PySide6.QtCore import QThread, Signal

from app.automation.sequence import AutomationStep

logger = logging.getLogger(__name__)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

user32 = ctypes.WinDLL("user32", use_last_error=True)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", MouseInput),
        ("ki", KeyboardInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", InputUnion),
    ]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

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


class UnicodeInputError(RuntimeError):
    """Raised when Unicode keyboard input could not be sent."""


def _requires_unicode_input(text: str) -> bool:
    return not text.isascii()


def _utf16_code_units(text: str) -> list[int]:
    raw = text.encode("utf-16-le")
    return [
        int.from_bytes(raw[index : index + 2], "little")
        for index in range(0, len(raw), 2)
    ]


def _send_unicode_code_unit(code_unit: int) -> None:
    events = (Input * 2)(
        Input(
            type=INPUT_KEYBOARD,
            union=InputUnion(
                ki=KeyboardInput(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=KEYEVENTF_UNICODE,
                    time=0,
                    dwExtraInfo=0,
                )
            ),
        ),
        Input(
            type=INPUT_KEYBOARD,
            union=InputUnion(
                ki=KeyboardInput(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                    time=0,
                    dwExtraInfo=0,
                )
            ),
        ),
    )
    sent_count = user32.SendInput(2, events, ctypes.sizeof(Input))
    if sent_count != 2:
        error_code = ctypes.get_last_error()
        raise UnicodeInputError(
            f"Unicode-Zeichen konnte nicht geschrieben werden. WinError {error_code}"
        )


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
                    self._write_text(step.value)
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

    def _write_text(self, text: str) -> None:
        if not _requires_unicode_input(text):
            pyautogui.write(text, interval=max(self.typing_interval / 3, 0.03))
            return

        interval = max(self.typing_interval / 3, 0.03)
        for code_unit in _utf16_code_units(text):
            self._ensure_not_aborted()
            _send_unicode_code_unit(code_unit)
            time.sleep(interval)

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
