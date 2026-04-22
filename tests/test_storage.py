import shutil
import tempfile
from pathlib import Path

from app.models.preferences import AppPreferences
from app.models.project_template import ProjectTemplate
from app.models.time_block import TimeBlock
from app.storage.json_store import JsonStorage


def make_test_dir(name: str) -> Path:
    root = Path("tests") / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{name}-", dir=root))


def test_save_and_load_day_blocks() -> None:
    temp_dir = make_test_dir("day")
    try:
        storage = JsonStorage(temp_dir)
        blocks = [
            TimeBlock(
                date="2026-04-15",
                start_time="06:30",
                end_time="10:00",
                block_type="work",
                project_number="25344",
                remark="Sys. Installation",
            ),
            TimeBlock(
                date="2026-04-15",
                start_time="12:00",
                end_time="13:00",
                block_type="break",
                project_number="",
                remark="Mittag",
            ),
        ]

        storage.save_day("2026-04-15", blocks)
        loaded = storage.load_day("2026-04-15")

        assert [block.to_dict() for block in loaded] == [block.to_dict() for block in blocks]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_and_load_templates() -> None:
    temp_dir = make_test_dir("templates")
    try:
        storage = JsonStorage(temp_dir)
        templates = [
            ProjectTemplate(project_number="25344", display_name="Muster", default_remark="Sys. Installation"),
            ProjectTemplate(project_number="27050", display_name="Admin", default_remark="Admin"),
        ]

        storage.save_templates(templates)
        loaded = storage.load_templates()

        assert [template.to_dict() for template in loaded] == [template.to_dict() for template in templates]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_and_load_preferences() -> None:
    temp_dir = make_test_dir("preferences")
    try:
        storage = JsonStorage(temp_dir)
        preferences = AppPreferences(
            last_project_number="25344",
            last_work_remark="Sys. Installation",
            countdown_seconds=5,
            typing_interval=0.2,
            project_badge_assignments={"25344": 2, "27050": 4},
        )

        storage.save_preferences(preferences)
        loaded = storage.load_preferences()

        assert loaded == preferences
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_seed_templates_are_loaded_when_missing() -> None:
    temp_dir = make_test_dir("seed")
    try:
        seed_file = temp_dir / "seed.json"
        seed_file.write_text(
            '[{"project_number":"26001","display_name":"AVOR","default_remark":"Sys. AVOR"}]',
            encoding="utf-8",
        )
        storage = JsonStorage(temp_dir / "data", seed_template_file=seed_file)

        loaded = storage.load_templates()

        assert len(loaded) == 1
        assert loaded[0].project_number == "26001"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
