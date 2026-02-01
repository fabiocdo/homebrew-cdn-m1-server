import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

os.environ["LOG_LEVEL"] = "debug"

from src.modules.auto_formatter import AutoFormatter
from tests.fixtures.fixtures import SFO_GAME, SFO_DLC, SFO_UPDATE, SFO_SAVE, SFO_UNKNOWN


class TestAutoFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = AutoFormatter()

    def test_normalize_value_title_uppercase(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_MODE": "uppercase"}, clear=False):
            self.assertEqual(self.formatter._normalize_value("title", "My Game"), "MY GAME")

    def test_normalize_value_title_lowercase(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_MODE": "lowercase"}, clear=False):
            self.assertEqual(self.formatter._normalize_value("title", "My Game"), "my game")

    def test_normalize_value_title_capitalize(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_MODE": "capitalize"}, clear=False):
            self.assertEqual(self.formatter._normalize_value("title", "my game"), "My Game")

    def test_normalize_value_title_capitalize_roman_numerals(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_MODE": "capitalize"}, clear=False):
            self.assertEqual(
                self.formatter._normalize_value("title", "final fantasy XII the zodiac age"),
                "Final Fantasy XII The Zodiac Age"
            )
            self.assertEqual(self.formatter._normalize_value("title", "resident evil III"), "Resident Evil III")
            self.assertEqual(self.formatter._normalize_value("title", "vincit omnia veritas"), "Vincit Omnia Veritas")

    def test_normalize_value_none(self):
        self.assertEqual(self.formatter._normalize_value("any", None), "")

    def test_normalize_value_other_key(self):
        self.assertEqual(self.formatter._normalize_value("title_id", "CUSA12345"), "CUSA12345")

    def test_normalize_value_numeric(self):
        self.assertEqual(self.formatter._normalize_value("version", 1.0), "1.0")
        self.assertEqual(self.formatter._normalize_value("title", 123), "123")

    def test_dry_run_not_found(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id} {app_type}"}, clear=False):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "test.pkg"
            mock_pkg.exists.return_value = False

            result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

            self.assertEqual(result, AutoFormatter.PlanResult.NOT_FOUND)
            self.assertEqual(planned_name, "test.pkg")

    def test_dry_run_invalid_empty_template(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_TEMPLATE": "{nonexistent}"}, clear=False):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "test.pkg"
            mock_pkg.exists.return_value = True

            result, planned_name = self.formatter.dry_run(mock_pkg, {"title": "Game"})

            self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
            self.assertEqual(planned_name, "test.pkg")

    def test_dry_run_invalid_no_data(self):
        with patch.dict(os.environ, {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id}"}, clear=False):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "test.pkg"
            mock_pkg.exists.return_value = True

            result, planned_name = self.formatter.dry_run(mock_pkg, {})

            self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
            self.assertEqual(planned_name, "test.pkg")

    def test_dry_run_skip_already_renamed(self):
        with patch.dict(
            os.environ,
            {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id} {app_type}", "AUTO_FORMATTER_MODE": "none"},
            clear=False,
        ):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "Horizon Zero Dawn CUSA01021 app.pkg"
            mock_pkg.exists.return_value = True

            result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

            self.assertEqual(result, AutoFormatter.PlanResult.SKIP)
            self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    def test_dry_run_conflict(self):
        with patch.dict(
            os.environ,
            {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id} {app_type}", "AUTO_FORMATTER_MODE": "none"},
            clear=False,
        ):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "old.pkg"
            mock_pkg.exists.return_value = True

            mock_target = MagicMock(spec=Path)
            mock_target.exists.return_value = True
            mock_pkg.with_name.return_value = mock_target

            result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

            self.assertEqual(result, AutoFormatter.PlanResult.CONFLICT)
            self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    def test_dry_run_ok(self):
        with patch.dict(
            os.environ,
            {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id} {app_type}", "AUTO_FORMATTER_MODE": "none"},
            clear=False,
        ):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "old.pkg"
            mock_pkg.exists.return_value = True

            mock_target = MagicMock(spec=Path)
            mock_target.exists.return_value = False
            mock_pkg.with_name.return_value = mock_target

            result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

            self.assertEqual(result, AutoFormatter.PlanResult.OK)
            self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    def test_dry_run_adds_pkg_extension(self):
        with patch.dict(
            os.environ,
            {"AUTO_FORMATTER_TEMPLATE": "{title}", "AUTO_FORMATTER_MODE": "none"},
            clear=False,
        ):
            mock_pkg = MagicMock(spec=Path)
            mock_pkg.name = "old.pkg"
            mock_pkg.exists.return_value = True

            mock_target = MagicMock(spec=Path)
            mock_target.exists.return_value = False
            mock_pkg.with_name.return_value = mock_target

            result, planned_name = self.formatter.dry_run(mock_pkg, {"title": "Game"})

            self.assertEqual(result, AutoFormatter.PlanResult.OK)
            self.assertEqual(planned_name, "Game.pkg")

    def test_dry_run_all_fixtures(self):
        with patch.dict(
            os.environ,
            {"AUTO_FORMATTER_TEMPLATE": "{title} {title_id} {app_type}", "AUTO_FORMATTER_MODE": "none"},
            clear=False,
        ):
            fixtures = [
                (SFO_GAME, "Horizon Zero Dawn CUSA01021 app.pkg"),
                (SFO_DLC, "The Frozen Wilds CUSA01021 addon.pkg"),
                (SFO_UPDATE, "Horizon Zero Dawn Update CUSA01021 patch.pkg"),
                (SFO_SAVE, "Horizon Zero Dawn Save Data CUSA01021 save.pkg"),
                (SFO_UNKNOWN, "Unknown Title XXXX00000 unknown.pkg"),
            ]

            for sfo, expected in fixtures:
                with self.subTest(sfo=sfo):
                    mock_pkg = MagicMock(spec=Path)
                    mock_pkg.name = "old.pkg"
                    mock_pkg.exists.return_value = True
                    mock_target = MagicMock(spec=Path)
                    mock_target.exists.return_value = False
                    mock_pkg.with_name.return_value = mock_target

                    result, planned_name = self.formatter.dry_run(mock_pkg, sfo)

                    self.assertEqual(result, AutoFormatter.PlanResult.OK)
                    self.assertEqual(planned_name, expected)

    def test_run_not_found(self):
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.exists.return_value = False

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.NOT_FOUND, "test.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    def test_run_invalid(self):
        mock_pkg = MagicMock(spec=Path)

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.INVALID, "test.pkg")):
            result = self.formatter.run(mock_pkg, {})

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    def test_run_skip(self):
        mock_pkg = MagicMock(spec=Path)

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.SKIP, "same.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    def test_run_conflict_moves_to_errors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"ERROR_DIR": tmp_dir}, clear=False):

                mock_pkg = MagicMock(spec=Path)
                mock_pkg.name = "old.pkg"
                mock_pkg.stem = "old"
                mock_pkg.suffix = ".pkg"

                with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.CONFLICT, "new.pkg")):
                    result = self.formatter.run(mock_pkg, SFO_GAME)

                    self.assertIsNone(result)
                    mock_pkg.rename.assert_called_once()

    def test_run_conflict_moves_to_errors_with_counter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"ERROR_DIR": tmp_dir}, clear=False):

                mock_pkg = MagicMock(spec=Path)
                mock_pkg.name = "old.pkg"
                mock_pkg.stem = "old"
                mock_pkg.suffix = ".pkg"

                first_path = Path(tmp_dir) / "old.pkg"
                first_path.touch()

                with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.CONFLICT, "new.pkg")):
                    result = self.formatter.run(mock_pkg, SFO_GAME)

                    self.assertIsNone(result)
                    args, _ = mock_pkg.rename.call_args
                    self.assertTrue(str(args[0]).endswith("old_1.pkg"))

    def test_run_ok_renames_successfully(self):
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"

        mock_target = MagicMock(spec=Path)
        mock_pkg.with_name.return_value = mock_target

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.OK, "new.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertEqual(result, "new.pkg")
            mock_pkg.with_name.assert_called_once_with("new.pkg")
            mock_pkg.rename.assert_called_once_with(mock_target)


if __name__ == "__main__":
    unittest.main()
