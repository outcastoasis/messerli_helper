from app.services.update_service import GitHubReleaseUpdater, clean_version, is_version_newer


class FakeUpdater(GitHubReleaseUpdater):
    def __init__(self, payload: dict, current_version: str = "0.1.6") -> None:
        super().__init__(current_version=current_version)
        self.payload = payload

    def _fetch_json(self, url: str) -> dict:
        return self.payload


def make_release_payload(version: str, asset_name: str) -> dict:
    return {
        "tag_name": f"v{version}",
        "name": f"Messerli Helper {version}",
        "html_url": f"https://github.com/outcastoasis/messerli_helper/releases/tag/v{version}",
        "published_at": "2026-04-22T08:00:00Z",
        "body": "Fehlerbehebungen und Verbesserungen.",
        "assets": [
            {
                "name": asset_name,
                "browser_download_url": f"https://github.com/outcastoasis/messerli_helper/releases/download/v{version}/{asset_name}",
                "size": 1024,
                "digest": "sha256:abc123",
            }
        ],
    }


def test_clean_version_removes_v_prefix() -> None:
    assert clean_version("v0.1.7") == "0.1.7"
    assert clean_version("0.1.7") == "0.1.7"


def test_is_version_newer_compares_numeric_parts() -> None:
    assert is_version_newer("0.1.10", "0.1.9") is True
    assert is_version_newer("0.1.6", "0.1.6") is False


def test_check_for_updates_returns_release_when_newer_installer_exists() -> None:
    updater = FakeUpdater(
        make_release_payload("0.1.7", "MesserliHelper-Setup-0.1.7.exe")
    )

    result = updater.check_for_updates()

    assert result.update_available is True
    assert result.update is not None
    assert result.update.version == "0.1.7"
    assert result.update.asset.name == "MesserliHelper-Setup-0.1.7.exe"


def test_check_for_updates_returns_error_when_expected_installer_is_missing() -> None:
    updater = FakeUpdater(make_release_payload("0.1.7", "notes.zip"))

    result = updater.check_for_updates()

    assert result.update_available is False
    assert "Installer" in result.error
