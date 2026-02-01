import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.modules.auto_formatter import AutoFormatter
from .fixtures import SFO_GAME, SFO_DLC, SFO_UPDATE, SFO_SAVE, SFO_UNKNOWN


class TestAutoFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = AutoFormatter()

    @patch('src.modules.auto_formatter.settings')
    def test_normalize_value_title_uppercase(self, mock_settings):
        mock_settings.AUTO_FORMATTER_MODE = "uppercase"
        self.assertEqual(self.formatter._normalize_value("title", "My Game"), "MY GAME")

    @patch('src.modules.auto_formatter.settings')
    def test_normalize_value_title_lowercase(self, mock_settings):
        mock_settings.AUTO_FORMATTER_MODE = "lowercase"
        self.assertEqual(self.formatter._normalize_value("title", "My Game"), "my game")

    @patch('src.modules.auto_formatter.settings')
    def test_normalize_value_title_capitalize(self, mock_settings):
        mock_settings.AUTO_FORMATTER_MODE = "capitalize"
        self.assertEqual(self.formatter._normalize_value("title", "my game"), "My Game")

    @patch('src.modules.auto_formatter.settings')
    def test_normalize_value_title_capitalize_roman_numerals(self, mock_settings):
        mock_settings.AUTO_FORMATTER_MODE = "capitalize"
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

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_not_found(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id} {app_type}"
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "test.pkg"
        mock_pkg.exists.return_value = False

        result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.NOT_FOUND)
        self.assertEqual(planned_name, "test.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_invalid_empty_template(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{nonexistent}"
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "test.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = self.formatter.dry_run(mock_pkg, {"title": "Game"})

        self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
        self.assertEqual(planned_name, "test.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_invalid_no_data(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id}"
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "test.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = self.formatter.dry_run(mock_pkg, {})

        self.assertEqual(result, AutoFormatter.PlanResult.INVALID)
        self.assertEqual(planned_name, "test.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_skip_already_renamed(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id} {app_type}"
        mock_settings.AUTO_FORMATTER_MODE = None
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "Horizon Zero Dawn CUSA01021 app.pkg"
        mock_pkg.exists.return_value = True

        result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.SKIP)
        self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_conflict(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id} {app_type}"
        mock_settings.AUTO_FORMATTER_MODE = None
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.exists.return_value = True

        mock_target = MagicMock(spec=Path)
        mock_target.exists.return_value = True
        mock_pkg.with_name.return_value = mock_target

        result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.CONFLICT)
        self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_ok(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id} {app_type}"
        mock_settings.AUTO_FORMATTER_MODE = None
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.exists.return_value = True

        mock_target = MagicMock(spec=Path)
        mock_target.exists.return_value = False
        mock_pkg.with_name.return_value = mock_target

        result, planned_name = self.formatter.dry_run(mock_pkg, SFO_GAME)

        self.assertEqual(result, AutoFormatter.PlanResult.OK)
        self.assertEqual(planned_name, "Horizon Zero Dawn CUSA01021 app.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_adds_pkg_extension(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title}"
        mock_settings.AUTO_FORMATTER_MODE = None
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.exists.return_value = True

        mock_target = MagicMock(spec=Path)
        mock_target.exists.return_value = False
        mock_pkg.with_name.return_value = mock_target

        result, planned_name = self.formatter.dry_run(mock_pkg, {"title": "Game"})

        self.assertEqual(result, AutoFormatter.PlanResult.OK)
        self.assertEqual(planned_name, "Game.pkg")

    @patch('src.modules.auto_formatter.settings')
    def test_dry_run_all_fixtures(self, mock_settings):
        mock_settings.AUTO_FORMATTER_TEMPLATE = "{title} {title_id} {app_type}"
        mock_settings.AUTO_FORMATTER_MODE = None

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

    @patch('src.modules.auto_formatter.settings')
    def test_run_not_found(self, mock_settings):
        mock_pkg = MagicMock(spec=Path)
        mock_pkg.exists.return_value = False

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.NOT_FOUND, "test.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    @patch('src.modules.auto_formatter.settings')
    def test_run_invalid(self, mock_settings):
        mock_pkg = MagicMock(spec=Path)

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.INVALID, "test.pkg")):
            result = self.formatter.run(mock_pkg, {})

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    @patch('src.modules.auto_formatter.settings')
    def test_run_skip(self, mock_settings):
        mock_pkg = MagicMock(spec=Path)

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.SKIP, "same.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_pkg.rename.assert_not_called()

    @patch('src.modules.auto_formatter.settings')
    def test_run_conflict_moves_to_errors(self, mock_settings):
        mock_error_dir = MagicMock(spec=Path)
        mock_settings.ERROR_DIR = mock_error_dir

        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.stem = "old"
        mock_pkg.suffix = ".pkg"

        mock_error_file = MagicMock(spec=Path)
        mock_error_file.exists.return_value = False
        mock_error_dir.__truediv__.return_value = mock_error_file

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.CONFLICT, "new.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_error_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_pkg.rename.assert_called_once()

    @patch('src.modules.auto_formatter.settings')
    def test_run_conflict_moves_to_errors_with_counter(self, mock_settings):
        mock_error_dir = MagicMock(spec=Path)
        mock_settings.ERROR_DIR = mock_error_dir

        mock_pkg = MagicMock(spec=Path)
        mock_pkg.name = "old.pkg"
        mock_pkg.stem = "old"
        mock_pkg.suffix = ".pkg"

        mock_error_file_1 = MagicMock(spec=Path)
        mock_error_file_1.exists.return_value = True

        mock_error_file_2 = MagicMock(spec=Path)
        mock_error_file_2.exists.return_value = False

        mock_error_dir.__truediv__.side_effect = [mock_error_file_1, mock_error_file_2]

        with patch.object(AutoFormatter, 'dry_run', return_value=(AutoFormatter.PlanResult.CONFLICT, "new.pkg")):
            result = self.formatter.run(mock_pkg, SFO_GAME)

            self.assertIsNone(result)
            mock_pkg.rename.assert_called_once_with(mock_error_file_2)

    @patch('src.modules.auto_formatter.settings')
    def test_run_ok_renames_successfully(self, mock_settings):
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