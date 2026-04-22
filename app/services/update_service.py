from __future__ import annotations

import hashlib
import json
import logging
import re
import ssl
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency during transition
    certifi = None

from app.metadata import (
    APP_EXECUTABLE_NAME,
    APP_GITHUB_LATEST_RELEASE_API_URL,
    APP_GITHUB_RELEASES_PAGE_URL,
    APP_GITHUB_REPOSITORY_SLUG,
    APP_INSTALLER_FILENAME_PREFIX,
    APP_NAME,
    APP_VERSION,
)

logger = logging.getLogger(__name__)

USER_AGENT = f"{APP_EXECUTABLE_NAME}/{APP_VERSION} ({APP_GITHUB_REPOSITORY_SLUG})"
VERSION_PART_PATTERN = re.compile(r"\d+")
DOWNLOAD_CHUNK_SIZE = 1024 * 256


class UpdateError(RuntimeError):
    """Raised when release metadata or downloads are invalid."""


@dataclass(slots=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    sha256: str = ""


@dataclass(slots=True)
class AppUpdate:
    version: str
    release_name: str
    release_url: str
    published_at: str
    notes: str
    asset: ReleaseAsset


@dataclass(slots=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str | None = None
    update: AppUpdate | None = None
    error: str = ""

    @property
    def update_available(self) -> bool:
        return self.update is not None


def clean_version(value: str) -> str:
    normalized = value.strip()
    if normalized.lower().startswith("v") and normalized[1:2].isdigit():
        normalized = normalized[1:]
    return normalized


def version_parts(value: str) -> tuple[int, ...]:
    normalized = clean_version(value)
    parts = tuple(int(match) for match in VERSION_PART_PATTERN.findall(normalized))
    if not parts:
        raise ValueError(f"Ungueltige Versionsangabe: {value!r}")
    return parts


def is_version_newer(candidate: str, current: str) -> bool:
    candidate_parts = version_parts(candidate)
    current_parts = version_parts(current)
    length = max(len(candidate_parts), len(current_parts))
    left = candidate_parts + (0,) * (length - len(candidate_parts))
    right = current_parts + (0,) * (length - len(current_parts))
    return left > right


class GitHubReleaseUpdater:
    def __init__(
        self,
        api_url: str = APP_GITHUB_LATEST_RELEASE_API_URL,
        releases_page_url: str = APP_GITHUB_RELEASES_PAGE_URL,
        current_version: str = APP_VERSION,
        installer_prefix: str = APP_INSTALLER_FILENAME_PREFIX,
    ) -> None:
        self.api_url = api_url
        self.releases_page_url = releases_page_url
        self.current_version = current_version
        self.installer_prefix = installer_prefix

    def check_for_updates(self) -> UpdateCheckResult:
        try:
            payload = self._fetch_json(self.api_url)
            update = self._build_update(payload)
        except UpdateError as exc:
            logger.warning("Update check failed: %s", exc)
            return UpdateCheckResult(
                current_version=self.current_version,
                error=str(exc),
            )

        if update is None:
            return UpdateCheckResult(current_version=self.current_version)

        return UpdateCheckResult(
            current_version=self.current_version,
            latest_version=update.version,
            update=update,
        )

    def download_update(
        self,
        update: AppUpdate,
        target_dir: Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        download_dir = Path(target_dir) if target_dir else self.default_download_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        installer_path = download_dir / update.asset.name

        request = Request(
            update.asset.download_url,
            headers={
                "Accept": "application/octet-stream",
                "User-Agent": USER_AGENT,
            },
        )
        expected_size = max(0, int(update.asset.size))
        downloaded = 0
        hasher = hashlib.sha256()
        ssl_context = self._create_ssl_context()

        try:
            with urlopen(request, timeout=30, context=ssl_context) as response:
                total = self._resolve_total_size(response, expected_size)
                with installer_path.open("wb") as handle:
                    while True:
                        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)
        except (HTTPError, URLError, OSError) as exc:
            installer_path.unlink(missing_ok=True)
            raise UpdateError(
                f"Download der neuen Version fehlgeschlagen: {exc}"
            ) from exc

        if expected_size and downloaded != expected_size:
            installer_path.unlink(missing_ok=True)
            raise UpdateError(
                "Der Installer wurde unvollstaendig heruntergeladen."
            )

        expected_sha256 = update.asset.sha256.strip().lower()
        if expected_sha256:
            actual_sha256 = hasher.hexdigest().lower()
            if actual_sha256 != expected_sha256:
                installer_path.unlink(missing_ok=True)
                raise UpdateError(
                    "Die heruntergeladene Datei passt nicht zur erwarteten SHA256-Pruefsumme."
                )

        return installer_path

    def launch_installer(self, installer_path: Path) -> None:
        try:
            subprocess.Popen(
                [
                    str(installer_path),
                    "/SP-",
                    "/CLOSEAPPLICATIONS",
                    "/NORESTART",
                ],
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError(
                f"Der Installer konnte nicht gestartet werden: {exc}"
            ) from exc

    @staticmethod
    def default_download_dir() -> Path:
        return Path(tempfile.gettempdir()) / APP_NAME / "updates"

    @staticmethod
    def _resolve_total_size(response, fallback_size: int) -> int:
        header = response.headers.get("Content-Length", "")
        if header.isdigit():
            return int(header)
        return fallback_size

    def _fetch_json(self, url: str) -> dict:
        ssl_context = self._create_ssl_context()
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urlopen(request, timeout=15, context=ssl_context) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 404:
                raise UpdateError(
                    "Es wurde noch kein GitHub Release fuer die App gefunden."
                ) from exc
            raise UpdateError(
                f"GitHub Releases konnte nicht gelesen werden (HTTP {exc.code})."
            ) from exc
        except URLError as exc:
            raise UpdateError(
                f"GitHub Releases ist gerade nicht erreichbar: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise UpdateError(
                "Die Antwort von GitHub Releases konnte nicht gelesen werden."
            ) from exc

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()

        # OpenSSL 3 can reject otherwise trusted chains more aggressively when
        # strict X.509 checking is enabled. We keep certificate verification on,
        # but relax this specific strictness flag for broader real-world compatibility.
        strict_flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
        if strict_flag:
            context.verify_flags &= ~strict_flag

        if certifi is not None:
            context.load_verify_locations(certifi.where())
        return context

    def _build_update(self, payload: dict) -> AppUpdate | None:
        latest_version = self._extract_release_version(payload)
        if not is_version_newer(latest_version, self.current_version):
            return None

        asset = self._select_asset(payload, latest_version)
        release_name = str(payload.get("name") or f"{APP_NAME} {latest_version}").strip()
        notes = str(payload.get("body") or "").strip()
        release_url = str(payload.get("html_url") or self.releases_page_url)
        published_at = str(payload.get("published_at") or "")

        return AppUpdate(
            version=latest_version,
            release_name=release_name,
            release_url=release_url,
            published_at=published_at,
            notes=notes,
            asset=asset,
        )

    def _extract_release_version(self, payload: dict) -> str:
        for key in ("tag_name", "name"):
            raw_value = str(payload.get(key) or "").strip()
            if not raw_value:
                continue
            normalized = clean_version(raw_value)
            if VERSION_PART_PATTERN.search(normalized):
                return normalized
        raise UpdateError("Das GitHub Release enthaelt keine gueltige Versionsnummer.")

    def _select_asset(self, payload: dict, version: str) -> ReleaseAsset:
        assets = payload.get("assets", [])
        if not isinstance(assets, list) or not assets:
            raise UpdateError(
                "Im GitHub Release wurde kein Installer-Asset gefunden."
            )

        expected_name = f"{self.installer_prefix}{version}.exe"
        normalized_assets = [self._normalize_asset(item) for item in assets]

        for asset in normalized_assets:
            if asset.name == expected_name:
                return asset

        for asset in normalized_assets:
            if (
                asset.name.startswith(self.installer_prefix)
                and asset.name.lower().endswith(".exe")
            ):
                return asset

        raise UpdateError(
            f"Im GitHub Release fehlt der erwartete Installer {expected_name}."
        )

    @staticmethod
    def _normalize_asset(payload: dict) -> ReleaseAsset:
        name = str(payload.get("name") or "").strip()
        download_url = str(payload.get("browser_download_url") or "").strip()
        if not name or not download_url:
            raise UpdateError("Ein GitHub Release Asset ist unvollstaendig.")

        digest = str(payload.get("digest") or "").strip().lower()
        sha256 = ""
        if digest.startswith("sha256:"):
            sha256 = digest.split(":", 1)[1]

        return ReleaseAsset(
            name=name,
            download_url=download_url,
            size=int(payload.get("size") or 0),
            sha256=sha256,
        )
