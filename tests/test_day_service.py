import shutil
import tempfile
from pathlib import Path

from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
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


def test_project_badge_assignments_fill_free_colors_first() -> None:
    temp_dir = make_test_dir("badge-colors")
    try:
        service = DayService(JsonStorage(temp_dir))
        templates = [
            ProjectTemplate(project_number="25344"),
            ProjectTemplate(project_number="27050"),
            ProjectTemplate(project_number="28000"),
        ]
        preferences = AppPreferences(
            project_badge_assignments={
                "27050": 5,
                "legacy-project": 1,
            }
        )

        changed = service.sync_project_badge_assignments(templates, preferences)

        assert changed is True
        assert preferences.project_badge_assignments == {
            "25344": 0,
            "27050": 5,
            "28000": 1,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_project_badge_assignment_is_reused_after_template_deletion() -> None:
    temp_dir = make_test_dir("badge-color-reuse")
    try:
        service = DayService(JsonStorage(temp_dir))
        preferences = AppPreferences(
            project_badge_assignments={
                "25344": 0,
                "27050": 1,
            }
        )

        changed = service.sync_project_badge_assignments(
            [
                ProjectTemplate(project_number="25344"),
                ProjectTemplate(project_number="28000"),
            ],
            preferences,
        )

        assert changed is True
        assert preferences.project_badge_assignments == {
            "25344": 0,
            "28000": 1,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
