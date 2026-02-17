from __future__ import annotations

import urllib.request
from http.client import HTTPResponse
from pathlib import Path
from typing import cast, final

from github import Github


@final
class GithubAssetsGateway:
    def __init__(self, repo_name: str = "LightningMods/PS4-Store") -> None:
        self._repo_name = repo_name

    def download_latest_release_assets(self, destinations: list[Path]) -> tuple[list[Path], list[Path]]:
        client = Github(timeout=10, retry=0)
        repo = client.get_repo(self._repo_name)
        release = repo.get_releases()[0]

        assets = {
            asset.name: asset.browser_download_url
            for asset in release.get_assets()
            if asset.name and asset.browser_download_url
        }

        downloaded: list[Path] = []
        missing: list[Path] = []
        for dest in destinations:
            if dest.exists():
                continue
            url = assets.get(dest.name)
            if not url:
                missing.append(dest)
                continue
            self._download(url, dest)
            downloaded.append(dest)
        return downloaded, missing

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".part")
        req = urllib.request.Request(url)
        response_obj = cast(HTTPResponse, urllib.request.urlopen(req, timeout=60))
        with response_obj as response:
            payload = response.read()
            _ = tmp.write_bytes(payload)
        _ = tmp.replace(destination)
