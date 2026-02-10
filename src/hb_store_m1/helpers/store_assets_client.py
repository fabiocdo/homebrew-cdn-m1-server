import urllib.request
from pathlib import Path

from github import Github

from hb_store_m1.models.globals import Globals
from hb_store_m1.utils.log_utils import LogUtils

UPDATE_REPO = "LightningMods/PS4-Store"


class StoreAssetClient:

    @staticmethod
    def download_store_assets() -> list[str]:

        client = Github()
        repo = client.get_repo(UPDATE_REPO)
        release = repo.get_releases()[0]

        release_assets = {
            asset.name: asset.browser_download_url
            for asset in release.get_assets()
            if asset.name and asset.browser_download_url
        }

        assets = (
            Globals.FILES.HOMEBREW_ELF_FILE_PATH,
            Globals.FILES.HOMEBREW_ELF_SIG_FILE_PATH,
            Globals.FILES.REMOTE_MD5_FILE_PATH,
            # Globals.FILES.STORE_PRX_FILE_PATH,
            # Globals.FILES.STORE_PRX_SIG_FILE_PATH,
        )

        downloaded = []

        for asset in assets:
            if not asset.exists():
                asset_url = release_assets.get(asset.name)

                if not asset_url:
                    LogUtils.log_warn(f"Asset {asset.name} not found in release")
                    continue

                dest = Globals.PATHS.CACHE_DIR_PATH / asset.name
                StoreAssetClient._download(asset_url, dest)

                LogUtils.log_debug(f"Asset {asset.name} downloaded successfully")
                downloaded.append(asset)

        return downloaded

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        user_agent = Globals.ENVS.APP_NAME
        headers = {"User-Agent": user_agent}
        req = urllib.request.Request(url, headers=headers)

        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = destination.with_suffix(destination.suffix + ".part")

        with urllib.request.urlopen(req, timeout=60) as response:
            tmp_path.write_bytes(response.read())

        tmp_path.replace(destination)


StoreAssetClient = StoreAssetClient()
