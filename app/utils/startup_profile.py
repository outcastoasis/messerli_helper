from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from app.utils.paths import get_default_data_dir

_PROFILE_ENV = "MESSERLI_STARTUP_PROFILE"
_PROFILE_DIR_ENV = "MESSERLI_STARTUP_PROFILE_DIR"
_AUTO_EXIT_ENV = "MESSERLI_STARTUP_AUTO_EXIT_MS"
_PROFILE_FILE_NAME = "startup_profile.jsonl"


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class StartupProfiler:
    def __init__(self) -> None:
        self.enabled = _is_truthy(os.environ.get(_PROFILE_ENV))
        self._started_at = time.perf_counter()
        self._log_file = self._resolve_log_file() if self.enabled else None

    def checkpoint(self, name: str, **details: Any) -> None:
        if not self.enabled or self._log_file is None:
            return

        payload: dict[str, Any] = {
            "checkpoint": name,
            "elapsed_ms": round((time.perf_counter() - self._started_at) * 1000, 3),
        }
        if details:
            payload["details"] = details

        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        with self._log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _resolve_log_file(self) -> Path:
        override_dir = os.environ.get(_PROFILE_DIR_ENV)
        if override_dir:
            return Path(override_dir) / _PROFILE_FILE_NAME
        return get_default_data_dir() / "logs" / _PROFILE_FILE_NAME


def get_auto_exit_delay_ms() -> int | None:
    raw_value = os.environ.get(_AUTO_EXIT_ENV)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        delay_ms = int(raw_value)
    except ValueError:
        return None
    return max(0, delay_ms)
