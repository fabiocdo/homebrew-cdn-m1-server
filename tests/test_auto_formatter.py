import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

os.environ["LOG_LEVEL"] = "debug"

from src.modules.auto_formatter import AutoFormatter
from tests.fixtures.fixtures import SFO_GAME


class TestAutoFormatter(unittest.TestCase):
    def test_dry_run_invalid_missing_content_id(self):
        formatter = AutoFormatter()
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "test.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = dry_run(mock_pkg, {"title": "Game"})

        self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
        self.assertEqual(planned_name, "test.pkg")

    def test_dry_run_invalid_content_id_chars(self):
        formatter = AutoFormatter()
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "test.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = dry_run(mock_pkg, {"content_id": "BAD/ID"})

        self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
        self.assertEqual(planned_name, "test.pkg")

    def test_dry_run_skip_already_renamed(self):
        formatter = AutoFormatter()
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = f"{SFO_GAME['content_id']}.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.SKIP)
        self.assertEqual(planned_name, f"{SFO_GAME['content_id']}.pkg")

    def test_dry_run_ok(self):
        formatter = AutoFormatter()
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.exists.return_value = True

        mock_target = MagicMock(spec=Path)
        mock_target.exists.return_value = False
        mock_pkg.with_name.return_value = mock_target

        result, planned_name = dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.OK)
        self.assertEqual(planned_name, f"{SFO_GAME['content_id']}.pkg")

    def test_run_conflict_moves_to_errors(self):
        formatter = AutoFormatter()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"ERROR_DIR": tmp_dir}, clear=False):

                mock_pkg = MagicMock(spec=Path)
                mock_pkg.name = "old.pkg"
                mock_pkg.stem = "old"
                mock_pkg.suffix = ".pkg"

                with patch.object(AutoFormatter, "dry_run", return_value=(AutoFormatter.PlanResult.CONFLICT, "new.pkg")):
                    result = run(mock_pkg, SFO_GAME)

                    self.assertIsNone(result)
                    mock_pkg.rename.assert_called_once()

    def test_run_ok_renames_successfully(self):
        formatter = AutoFormatter()
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"

        mock_target = MagicMock(spec=Path)
        mock_pkg.with_name.return_value = mock_target

        with patch.object(AutoFormatter, "dry_run", return_value=(AutoFormatter.PlanResult.OK, "new.pkg")):
            result = run(mock_pkg, SFO_GAME)

            self.assertEqual(result, "new.pkg")
            mock_pkg.with_name.assert_called_once_with("new.pkg")
            mock_pkg.rename.assert_called_once_with(mock_target)


if __name__ == "__main__":
    unittest.main()
