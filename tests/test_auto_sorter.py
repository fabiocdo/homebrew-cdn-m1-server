import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

os.environ["LOG_LEVEL"] = "debug"

from src.modules.auto_sorter import AutoSorter


class TestAutoSorter(unittest.TestCase):
    def setUp(self):
        self.sorter = AutoSorter()

    def test_category_map(self):
        expected_map = {
            "ac": "dlc",
            "gc": "game",
            "gd": "game",
            "gp": "update",
            "sd": "save",
        }
        self.assertEqual(AutoSorter.CATEGORY_MAP, expected_map)

    def test_dry_run_not_found(self):
        with patch.dict(os.environ, {"PKG_DIR": "/data/pkg"}, clear=False):
            pkg = MagicMock(spec=Path)
            pkg.exists.return_value = False

            result, target_dir = self.sorter.dry_run(pkg, "gd")

            self.assertEqual(result, AutoSorter.PlanResult.NOT_FOUND)
            self.assertIsNone(target_dir)

    def test_dry_run_skip(self):
        with patch.dict(os.environ, {"PKG_DIR": "/data/pkg"}, clear=False):
            pkg = MagicMock(spec=Path)
            pkg.exists.return_value = True
            pkg.name = "game.pkg"
            pkg.parent = Path("/data/pkg/game")

            result, target_dir = self.sorter.dry_run(pkg, "gd")
            self.assertEqual(result, AutoSorter.PlanResult.SKIP)
            self.assertEqual(target_dir, Path("/data/pkg/game"))

    def test_dry_run_conflict(self):
        with patch.dict(os.environ, {"PKG_DIR": "/data/pkg"}, clear=False):
            pkg = MagicMock(spec=Path)
            pkg.exists.return_value = True
            pkg.name = "game.pkg"
            pkg.parent = Path("/data/pkg/other")

            with patch('pathlib.Path.exists', return_value=True):
                result, target_dir = self.sorter.dry_run(pkg, "gd")
                self.assertEqual(result, AutoSorter.PlanResult.CONFLICT)

    def test_dry_run_ok(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg = MagicMock(spec=Path)
                pkg.exists.return_value = True
                pkg.name = "game.pkg"
                pkg.parent = Path(tmp_dir) / "other"

                result, _ = self.sorter.dry_run(pkg, "gd")
                self.assertEqual(result, AutoSorter.PlanResult.OK)

    def test_run_not_found(self):
        pkg = MagicMock(spec=Path)
        with patch.object(AutoSorter, 'dry_run', return_value=(AutoSorter.PlanResult.NOT_FOUND, None)):
            result = self.sorter.run(pkg, "gd")
            self.assertIsNone(result)
            pkg.rename.assert_not_called()

    def test_run_skip(self):
        pkg = MagicMock(spec=Path)
        target_dir = Path("/data/pkg/game")
        with patch.object(AutoSorter, 'dry_run', return_value=(AutoSorter.PlanResult.SKIP, target_dir)):
            result = self.sorter.run(pkg, "gd")
            self.assertIsNone(result)
            pkg.rename.assert_not_called()

    def test_run_conflict_moves_to_errors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"ERROR_DIR": tmp_dir}, clear=False):
                pkg = MagicMock(spec=Path)
                pkg.name = "conflict.pkg"
                pkg.stem = "conflict"
                pkg.suffix = ".pkg"

                with patch.object(AutoSorter, 'dry_run', return_value=(AutoSorter.PlanResult.CONFLICT, Path("/data/pkg/game"))):
                    result = self.sorter.run(pkg, "gd")
                    self.assertIsNone(result)
                    pkg.rename.assert_called_once()

    def test_run_ok_moves_successfully(self):
        pkg = MagicMock(spec=Path)
        pkg.name = "game.pkg"

        target_dir = MagicMock(spec=Path)
        target_dir.name = "game"
        target_path = MagicMock(spec=Path)
        target_dir.__truediv__.return_value = target_path

        with patch.object(AutoSorter, 'dry_run', return_value=(AutoSorter.PlanResult.OK, target_dir)):
            result = self.sorter.run(pkg, "gd")
            self.assertEqual(result, str(target_path))
            target_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            pkg.rename.assert_called_once_with(target_path)


if __name__ == "__main__":
    unittest.main()
