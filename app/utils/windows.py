from __future__ import annotations

import ctypes
import os
import sys


def set_current_process_app_user_model_id(app_user_model_id: str) -> bool:
    """Set an explicit AppUserModelID so shortcuts and taskbar grouping match."""
    if sys.platform != "win32":
        return False

    try:
        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        return set_app_id(app_user_model_id) >= 0
    except Exception:
        return False


def get_foreground_window_handle() -> int | None:
    """Return the current foreground window handle on Windows."""
    if sys.platform != "win32":
        return None

    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        handle = user32.GetForegroundWindow()
        return int(handle) if handle else None
    except Exception:
        return None


def get_window_process_id(window_handle: int | None) -> int | None:
    """Return the owning process id for a window handle."""
    if sys.platform != "win32" or not window_handle:
        return None

    try:
        process_id = ctypes.c_ulong()
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        thread_id = user32.GetWindowThreadProcessId(
            ctypes.c_void_p(window_handle), ctypes.byref(process_id)
        )
        if not thread_id or not process_id.value:
            return None
        return int(process_id.value)
    except Exception:
        return None


def is_current_process_window(window_handle: int | None) -> bool:
    """Check whether a window belongs to the current process."""
    process_id = get_window_process_id(window_handle)
    return process_id == os.getpid() if process_id is not None else False


def activate_window(window_handle: int | None) -> bool:
    """Restore and activate a top-level window."""
    if sys.platform != "win32" or not window_handle:
        return False

    try:
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [ctypes.c_void_p]
        user32.IsWindow.restype = ctypes.c_bool
        if not user32.IsWindow(ctypes.c_void_p(window_handle)):
            return False

        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.ShowWindow.restype = ctypes.c_bool
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        user32.SetForegroundWindow.restype = ctypes.c_bool

        user32.ShowWindow(ctypes.c_void_p(window_handle), 9)
        return bool(user32.SetForegroundWindow(ctypes.c_void_p(window_handle)))
    except Exception:
        return False
