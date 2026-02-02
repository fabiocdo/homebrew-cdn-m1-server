from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Iterable


class UpdateFetcher:
    """
    Fetch update assets from a GitHub releases endpoint.

    :param source_url: GitHub releases API URL
    :param required_files: Iterable of required asset file names
    :param optional_files: Iterable of optional asset file names
    """

    def __init__(
        self,
        source_url: str,
        required_files: Iterable[str],
        optional_files: Iterable[str] | None = None,
    ):
        """
        Initialize the update fetcher.

        :param source_url: GitHub releases API URL
        :param required_files: Iterable of required asset file names
        :param optional_files: Iterable of optional asset file names
        :return: None
        """
        self.source_url = source_url
        self.required_files = list(required_files)
        self.optional_files = list(optional_files or [])

    def ensure_assets(self, cache_dir: Path) -> dict:
        """
        Ensure assets exist under cache_dir, downloading missing files.

        :param cache_dir: Directory where update assets should be stored
        :return: Dict with keys: missing_required, missing_optional,
            downloaded, unavailable_required, unavailable_optional, errors
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        missing_required = [name for name in self.required_files if not (cache_dir / name).exists()]
        missing_optional = [name for name in self.optional_files if not (cache_dir / name).exists()]
        if not missing_required and not missing_optional:
            return {
                "missing_required": [],
                "missing_optional": [],
                "downloaded": [],
                "unavailable_required": [],
                "unavailable_optional": [],
                "errors": [],
            }

        assets = self._fetch_release_assets()
        downloaded = []
        unavailable_required = []
        unavailable_optional = []
        errors = []

        for name in missing_required + missing_optional:
            url = assets.get(name)
            if not url:
                if name in missing_required:
                    unavailable_required.append(name)
                else:
                    unavailable_optional.append(name)
                continue
            try:
                self._download(url, cache_dir / name)
                downloaded.append(name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        return {
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "downloaded": downloaded,
            "unavailable_required": unavailable_required,
            "unavailable_optional": unavailable_optional,
            "errors": errors,
        }

    def _fetch_release_assets(self) -> dict:
        """
        Fetch the latest release asset map from GitHub.

        :return: Dict of asset name to download URL
        """
        headers = {
            "User-Agent": "homebrew-store-cdn",
            "Accept": "application/vnd.github+json",
        }
        req = urllib.request.Request(self.source_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.load(resp)

        if isinstance(payload, dict) and payload.get("message"):
            raise RuntimeError(payload["message"])

        if not isinstance(payload, list) or not payload:
            raise RuntimeError("No releases returned from GitHub")

        release = payload[0]
        assets = release.get("assets", [])
        return {
            asset.get("name"): asset.get("browser_download_url")
            for asset in assets
            if asset.get("name") and asset.get("browser_download_url")
        }

    @staticmethod
    def _download(url: str, dest: Path) -> None:
        """
        Download a file from url to dest.

        :param url: Download URL
        :param dest: Destination path
        :return: None
        """
        headers = {"User-Agent": "homebrew-store-cdn"}
        req = urllib.request.Request(url, headers=headers)
        tmp_path = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(req, timeout=60) as resp:
            tmp_path.write_bytes(resp.read())
        tmp_path.replace(dest)
