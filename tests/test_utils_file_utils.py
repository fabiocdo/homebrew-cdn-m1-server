from hb_store_m1.models.log import LogModule
from hb_store_m1.utils.file_utils import FileUtils


def test_given_existing_file_when_move_then_moves_to_target(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("data", encoding="utf-8")
    target = tmp_path / "dest" / "target.txt"

    moved = FileUtils.move(source, target, LogModule.PKG_UTIL)

    assert moved == target
    assert target.exists()
    assert not source.exists()


def test_given_existing_file_when_move_to_error_then_appends_counter(tmp_path):
    errors_dir = tmp_path / "errors"
    original = tmp_path / "pkg.pkg"
    original.write_text("data", encoding="utf-8")

    existing = errors_dir / "pkg.pkg"
    errors_dir.mkdir(parents=True, exist_ok=True)
    existing.write_text("old", encoding="utf-8")

    moved = FileUtils.move_to_error(
        original, errors_dir, "test", LogModule.WATCHER
    )

    assert moved is not None
    assert moved.name == "pkg_1.pkg"
    assert moved.exists()
    assert not original.exists()


def test_given_png_when_optimize_png_then_keeps_or_reduces_size(sample_png):
    original_size = sample_png.stat().st_size

    optimized = FileUtils.optimize_png(sample_png, LogModule.PKG_UTIL)

    assert optimized is False
    assert sample_png.exists()
    assert sample_png.stat().st_size == original_size
