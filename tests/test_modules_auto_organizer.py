from pathlib import Path

from hb_store_m1.models.output import Status
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.modules.auto_organizer import AutoOrganizer


def test_given_missing_pkg_when_dry_run_then_returns_not_found(temp_globals):
    pkg = PKG(
        content_id="X",
        category="GD",
        pkg_path=temp_globals.GAME_DIR_PATH / "missing.pkg",
    )
    result = AutoOrganizer.dry_run(pkg)

    assert result.status is Status.NOT_FOUND


def test_given_invalid_content_id_when_dry_run_then_returns_invalid(
    sample_pkg_file,
):
    pkg = PKG(content_id="", category="GD", pkg_path=sample_pkg_file)
    result = AutoOrganizer.dry_run(pkg)

    assert result.status is Status.INVALID


def test_given_valid_content_id_when_dry_run_then_returns_target_path(
    init_paths, sample_pkg_file
):
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pkg_path=sample_pkg_file,
    )

    result = AutoOrganizer.dry_run(pkg)

    assert result.status is Status.OK
    assert str(result.content).endswith(".pkg")
    assert init_paths.GAME_DIR_PATH.as_posix() in str(result.content)


def test_given_pkg_already_in_place_when_run_then_returns_path(
    init_paths,
):
    pkg_path = init_paths.GAME_DIR_PATH / "UP0000-TEST00000_00-TEST000000000000.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pkg_path=pkg_path,
    )

    result = AutoOrganizer.run(pkg)

    assert result == pkg_path
    assert pkg_path.exists()


def test_given_pkg_when_run_then_moves_and_renames(
    init_paths,
):
    pkg_path = init_paths.PKG_DIR_PATH / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pkg_path=pkg_path,
    )

    result = AutoOrganizer.run(pkg)

    assert result is not None
    assert result.exists()
    assert result.name.startswith("UP0000-TEST00000")


def test_given_invalid_filename_when_dry_run_then_returns_invalid(init_paths):
    pkg_path = init_paths.GAME_DIR_PATH / "bad*name.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    pkg = PKG(
        content_id="UP0000-TEST00000_00-TEST000000000000",
        category="GD",
        pkg_path=pkg_path,
    )

    result = AutoOrganizer.dry_run(pkg)

    assert result.status is Status.INVALID


def test_given_dry_run_not_found_when_run_then_returns_none(monkeypatch):
    pkg = PKG(content_id="X", category="GD", pkg_path=Path(__file__))
    monkeypatch.setattr(
        AutoOrganizer,
        "dry_run",
        lambda _pkg: type("R", (), {"status": Status.NOT_FOUND, "content": None})(),
    )

    assert AutoOrganizer.run(pkg) is None


def test_given_dry_run_invalid_when_run_then_returns_none(monkeypatch):
    pkg = PKG(content_id="X", category="GD", pkg_path=Path(__file__))
    monkeypatch.setattr(
        AutoOrganizer,
        "dry_run",
        lambda _pkg: type("R", (), {"status": Status.INVALID, "content": None})(),
    )

    assert AutoOrganizer.run(pkg) is None


def test_given_dry_run_conflict_when_run_then_returns_none(monkeypatch, tmp_path):
    pkg = PKG(content_id="X", category="GD", pkg_path=tmp_path / "x.pkg")
    monkeypatch.setattr(
        AutoOrganizer,
        "dry_run",
        lambda _pkg: type(
            "R", (), {"status": Status.CONFLICT, "content": tmp_path / "target.pkg"}
        )(),
    )

    assert AutoOrganizer.run(pkg) is None


def test_given_missing_target_path_when_run_then_returns_none(monkeypatch, tmp_path):
    pkg_path = tmp_path / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")
    pkg = PKG(content_id="X", category="GD", pkg_path=pkg_path)
    monkeypatch.setattr(
        AutoOrganizer,
        "dry_run",
        lambda _pkg: type("R", (), {"status": Status.OK, "content": None})(),
    )

    assert AutoOrganizer.run(pkg) is None
