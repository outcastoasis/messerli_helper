from __future__ import annotations

import ctypes
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
