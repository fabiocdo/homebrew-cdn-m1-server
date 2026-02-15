import urllib.request
from pathlib import Path

from github import Github

from hb_store_m1.models.globals import Globals


class StoreAssetClient:

    @staticmethod
    def download_store_assets(assets: list[Path]) -> tuple[list[Path], list[Path]]:
        assets_repo = "LightningMods/PS4-Store"
        client = Github(timeout=10, retry=0)

        repo = client.get_repo(assets_repo)
        release = repo.get_releases()[0]

        release_assets = {
            asset.name: asset.browser_download_url
            for asset in release.get_assets()
            if asset.name and asset.browser_download_url
        }

        downloaded = []
        missing = []

        for asset in assets:
            if not asset.exists():
                asset_url = release_assets.get(asset.name)

                if not asset_url:
                    missing.append(asset)
                    continue

                dest = Globals.PATHS.CACHE_DIR_PATH / asset.name
                StoreAssetClient._download(asset_url, dest)

                downloaded.append(asset)

        return downloaded, missing

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        req = urllib.request.Request(url)

        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = destination.with_suffix(destination.suffix + ".part")

        with urllib.request.urlopen(req, timeout=60) as response:
            tmp_path.write_bytes(response.read())

        tmp_path.replace(destination)
