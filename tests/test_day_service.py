import shutil
import tempfile
from pathlib import Path

from app.models.time_block import TimeBlock
from app.services.day_service import DayService
from app.storage.json_store import JsonStorage


def make_test_dir(name: str) -> Path:
    root = Path("tests") / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{name}-", dir=root))


def test_productive_summary_counts_work_and_compensation_only() -> None:
    temp_dir = make_test_dir("productivity")
    try:
        service = DayService(JsonStorage(temp_dir))
        blocks = [
            TimeBlock(
                date="2026-04-13",
                start_time="08:00",
                end_time="12:00",
                block_type="work",
                project_number="25344",
                remark="Sys. Installation",
            ),
            TimeBlock(
                date="2026-04-13",
                start_time="12:00",
                end_time="12:30",
                block_type="break",
                project_number="",
                remark="Mittag",
            ),
            TimeBlock(
                date="2026-04-13",
                start_time="12:30",
                end_time="17:00",
                block_type="compensation",
                project_number="",
                remark="Kompensation",
            ),
        ]

        summary = service.productive_time_summary("2026-04-13", blocks)

        assert summary.productive_minutes == 510
        assert summary.target_minutes == 510
        assert summary.difference_minutes == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_productive_target_is_eight_hours_on_friday() -> None:
    temp_dir = make_test_dir("productivity-friday")
    try:
        service = DayService(JsonStorage(temp_dir))
        assert service.target_productive_minutes("2026-04-17") == 480
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
