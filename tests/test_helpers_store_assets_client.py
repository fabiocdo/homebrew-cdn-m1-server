from pathlib import Path

from hb_store_m1.helpers.store_assets_client import StoreAssetClient
from hb_store_m1.models.globals import Globals


class _FakeAsset:
    def __init__(self, name, url):
        self.name = name
        self.browser_download_url = url


class _FakeRelease:
    def __init__(self, assets):
        self._assets = assets

    def get_assets(self):
        return self._assets


class _FakeRepo:
    def __init__(self, release):
        self._release = release

    def get_releases(self):
        return [self._release]


class _FakeGithub:
    def __init__(self, *args, **kwargs):
        self._repo = None

    def get_repo(self, _repo):
        return self._repo


def test_given_assets_when_one_missing_then_reports_missing_and_downloads_present(
    temp_globals, monkeypatch
):
    cache_dir = Globals.PATHS.CACHE_DIR_PATH
    asset_a = cache_dir / "a.bin"
    asset_b = cache_dir / "b.bin"

    fake_release = _FakeRelease(
        [
            _FakeAsset("a.bin", "http://example/a.bin"),
        ]
    )
    fake_repo = _FakeRepo(fake_release)
    fake_client = _FakeGithub()
    fake_client._repo = fake_repo

    monkeypatch.setattr(
        "hb_store_m1.helpers.store_assets_client.Github",
        lambda **_: fake_client,
    )

    downloaded = []

    def fake_download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"data")
        downloaded.append((url, dest))

    monkeypatch.setattr(StoreAssetClient, "_download", fake_download)

    downloaded_assets, missing_assets = StoreAssetClient.download_store_assets(
        [asset_a, asset_b]
    )

    assert downloaded_assets == [asset_a]
    assert missing_assets == [asset_b]
    assert downloaded
    assert (cache_dir / "a.bin").exists()


def test_given_download_url_when_download_then_writes_destination(
    temp_globals, monkeypatch
):
    destination = Globals.PATHS.CACHE_DIR_PATH / "file.bin"

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"payload"

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _FakeResponse()
    )

    StoreAssetClient._download("http://example/file.bin", destination)

    assert destination.exists()
    assert destination.read_bytes() == b"payload"
