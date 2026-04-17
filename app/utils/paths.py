from __future__ import annotations

import os
import sys
from pathlib import Path

from app.constants import APP_DATA_DIR_NAME


def get_bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DATA_DIR_NAME
    return Path.cwd() / ".messerli-helper-data"
