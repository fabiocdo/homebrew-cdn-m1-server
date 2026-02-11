from hb_store_m1.models.output import Status
from hb_store_m1.modules.auto_organizer import AutoOrganizer


def test_given_missing_pkg_when_dry_run_then_returns_not_found(temp_globals):
    result = AutoOrganizer.dry_run(
        temp_globals.GAME_DIR_PATH / "missing.pkg", {"content_id": "X"}
    )

    assert result.status is Status.NOT_FOUND


def test_given_invalid_content_id_when_dry_run_then_returns_invalid(
    sample_pkg_file,
):
    result = AutoOrganizer.dry_run(sample_pkg_file, {"content_id": ""})

    assert result.status is Status.INVALID


def test_given_valid_content_id_when_dry_run_then_returns_target_path(
    init_paths, sample_pkg_file
):
    sfo = {"content_id": "UP0000-TEST00000_00-TEST000000000000", "app_type": "game"}

    result = AutoOrganizer.dry_run(sample_pkg_file, sfo)

    assert result.status is Status.OK
    assert str(result.content).endswith(".pkg")
    assert init_paths.GAME_DIR_PATH.as_posix() in str(result.content)


def test_given_pkg_already_in_place_when_run_then_returns_path(
    init_paths,
):
    pkg_path = init_paths.GAME_DIR_PATH / "UP0000-TEST00000_00-TEST000000000000.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    result = AutoOrganizer.run(
        pkg_path,
        {"content_id": "UP0000-TEST00000_00-TEST000000000000", "app_type": "game"},
    )

    assert result == pkg_path
    assert pkg_path.exists()


def test_given_pkg_when_run_then_moves_and_renames(
    init_paths,
):
    pkg_path = init_paths.PKG_DIR_PATH / "raw.pkg"
    pkg_path.write_text("pkg", encoding="utf-8")

    result = AutoOrganizer.run(
        pkg_path,
        {"content_id": "UP0000-TEST00000_00-TEST000000000000", "app_type": "game"},
    )

    assert result is not None
    assert result.exists()
    assert result.name.startswith("UP0000-TEST00000")
