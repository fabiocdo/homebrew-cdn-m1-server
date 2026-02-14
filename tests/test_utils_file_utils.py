from hb_store_m1.utils.file_utils import FileUtils


def test_given_existing_file_when_move_then_moves_to_target(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("data", encoding="utf-8")
    target = tmp_path / "dest" / "target.txt"

    moved = FileUtils.move(source, target)

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

    moved = FileUtils.move_to_error(original, errors_dir, "test")

    assert moved is not None
    assert moved.name == "pkg_1.pkg"
    assert moved.exists()
    assert not original.exists()


def test_given_png_when_optimize_png_then_keeps_or_reduces_size(sample_png):
    original_size = sample_png.stat().st_size

    optimized = FileUtils.optimize_png(sample_png)

    assert optimized is False
    assert sample_png.exists()
    assert sample_png.stat().st_size == original_size


def test_given_missing_png_when_optimize_png_then_returns_false(tmp_path):
    assert FileUtils.optimize_png(tmp_path / "missing.png") is False


def test_given_multiple_conflicts_when_move_to_error_then_uses_next_counter(tmp_path):
    errors_dir = tmp_path / "errors"
    errors_dir.mkdir(parents=True, exist_ok=True)
    (errors_dir / "pkg.pkg").write_text("old", encoding="utf-8")
    (errors_dir / "pkg_1.pkg").write_text("old", encoding="utf-8")
    original = tmp_path / "pkg.pkg"
    original.write_text("data", encoding="utf-8")

    moved = FileUtils.move_to_error(original, errors_dir, "test")

    assert moved is not None
    assert moved.name == "pkg_2.pkg"


def test_given_rename_error_when_move_then_returns_none(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("data", encoding="utf-8")
    target = tmp_path / "dest" / "target.txt"

    def fake_rename(_self, _target):
        raise OSError("boom")

    monkeypatch.setattr(type(source), "rename", fake_rename)

    assert FileUtils.move(source, target) is None


def test_given_move_failure_when_move_to_error_then_returns_none(tmp_path, monkeypatch):
    source = tmp_path / "source.pkg"
    source.write_text("data", encoding="utf-8")
    errors_dir = tmp_path / "errors"

    monkeypatch.setattr(FileUtils, "move", lambda *_args, **_kwargs: None)

    assert FileUtils.move_to_error(source, errors_dir, "reason") is None
