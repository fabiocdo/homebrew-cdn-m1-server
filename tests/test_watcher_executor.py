import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.modules.helpers.watcher_executor import WatcherExecutor
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.models.watcher_models import PlanOutput
from tests.fixtures.fixtures import SFO_GAME


class TestWatcherExecutor(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._prev_error = os.environ.get("ERROR_DIR")
        self._prev_log = os.environ.get("LOG_DIR")
        os.environ["ERROR_DIR"] = self._temp_dir.name
        os.environ["LOG_DIR"] = self._temp_dir.name

    def tearDown(self):
        if self._prev_error is None:
            os.environ.pop("ERROR_DIR", None)
        else:
            os.environ["ERROR_DIR"] = self._prev_error
        if self._prev_log is None:
            os.environ.pop("LOG_DIR", None)
        else:
            os.environ["LOG_DIR"] = self._prev_log
        self._temp_dir.cleanup()

    def _make_executor(self):
        pkg_utils = MagicMock()
        formatter = MagicMock(spec=AutoFormatter)
        sorter = MagicMock(spec=AutoSorter)
        formatter.run.return_value = None
        sorter.run.return_value = None
        return WatcherExecutor(pkg_utils, formatter, sorter), pkg_utils, formatter, sorter

    def test_rejected_pkg_moves_to_error_and_logs(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as data_dir:
            error_dir = Path(data_dir) / "_error"
            pkg_dir = Path(data_dir) / "pkg"
            pkg_dir.mkdir(parents=True, exist_ok=True)
            pkg_path = pkg_dir / "bad.pkg"
            pkg_path.write_text("x", encoding="utf-8")

            log_dir = Path(data_dir) / "_logs"
            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir), "LOG_DIR": str(log_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg_path),
                        "pkg": {
                            "planned_path": str(pkg_path),
                            "action": PlanOutput.REJECT,
                            "reason": "formatter_conflict",
                        },
                        "icon": {"planned_path": None, "action": PlanOutput.REJECT},
                    }
                ]
                sfo_cache = {str(pkg_path): SFO_GAME}
                _, stats = executor.run(results, sfo_cache)

            moved_path = error_dir / "bad.pkg"
            self.assertTrue(moved_path.exists())
            self.assertEqual(stats["errors"], 1)
            log_path = log_dir / "errors.log"
            self.assertTrue(log_path.exists())
            self.assertIn("formatter_conflict", log_path.read_text(encoding="utf-8"))

    def test_rejected_missing_file_not_counted(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            log_dir = Path(tmp_dir) / "_logs"
            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir), "LOG_DIR": str(log_dir)}, clear=False):
                results = [
                    {
                        "source": str(Path(tmp_dir) / "missing.pkg"),
                        "pkg": {"planned_path": "", "action": PlanOutput.REJECT, "reason": "missing_sfo"},
                        "icon": {"planned_path": None, "action": PlanOutput.REJECT},
                    }
                ]
                sfo_cache = {}
                _, stats = executor.run(results, sfo_cache)

            self.assertEqual(stats["errors"], 0)
            self.assertTrue(error_dir.exists())
            self.assertFalse((log_dir / "errors.log").exists())

    def test_icon_extraction_success(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            pkg_path = Path(tmp_dir) / "a.pkg"
            pkg_path.write_text("x", encoding="utf-8")
            icon_path = Path(tmp_dir) / "icon.png"

            def extract_side_effect(path, content_id, dry_run=False):
                icon_path.write_text("img", encoding="utf-8")
                return icon_path

            pkg_utils.extract_pkg_icon.side_effect = extract_side_effect

            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg_path),
                        "pkg": {"planned_path": str(pkg_path), "action": PlanOutput.ALLOW},
                        "icon": {"planned_path": str(icon_path), "action": PlanOutput.ALLOW},
                    }
                ]
                sfo_cache = {str(pkg_path): SFO_GAME}
                _, stats = executor.run(results, sfo_cache)

            self.assertEqual(stats["extractions"], 1)
            self.assertTrue(icon_path.exists())

    def test_icon_extraction_failure(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            pkg_path = Path(tmp_dir) / "a.pkg"
            pkg_path.write_text("x", encoding="utf-8")
            icon_path = Path(tmp_dir) / "icon.png"

            pkg_utils.extract_pkg_icon.return_value = None

            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg_path),
                        "pkg": {"planned_path": str(pkg_path), "action": PlanOutput.ALLOW},
                        "icon": {"planned_path": str(icon_path), "action": PlanOutput.ALLOW},
                    }
                ]
                sfo_cache = {str(pkg_path): SFO_GAME}
                _, stats = executor.run(results, sfo_cache)

            self.assertEqual(stats["extractions"], 0)

    def test_format_and_sort_counts(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            pkg_path = Path(tmp_dir) / "a.pkg"
            pkg_path.write_text("x", encoding="utf-8")

            formatter.run.return_value = "new.pkg"
            sorter.run.return_value = str(Path(tmp_dir) / "game" / "new.pkg")

            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg_path),
                        "pkg": {"planned_path": str(pkg_path), "action": PlanOutput.ALLOW},
                        "icon": {"planned_path": None, "action": PlanOutput.REJECT},
                    }
                ]
                sfo_cache = {str(pkg_path): SFO_GAME}
                _, stats = executor.run(results, sfo_cache)

            self.assertEqual(stats["renames"], 1)
            self.assertEqual(stats["moves"], 1)

    def test_skipped_count_excludes_rejected(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            pkg1 = Path(tmp_dir) / "a.pkg"
            pkg2 = Path(tmp_dir) / "b.pkg"
            pkg3 = Path(tmp_dir) / "c.pkg"
            pkg1.write_text("x", encoding="utf-8")
            pkg2.write_text("x", encoding="utf-8")
            pkg3.write_text("x", encoding="utf-8")

            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg1),
                        "pkg": {"planned_path": str(pkg1), "action": PlanOutput.SKIP},
                        "icon": {"planned_path": None, "action": PlanOutput.REJECT},
                    },
                    {
                        "source": str(pkg2),
                        "pkg": {"planned_path": str(pkg2), "action": PlanOutput.ALLOW},
                        "icon": {"planned_path": str(Path(tmp_dir) / "i.png"), "action": PlanOutput.SKIP},
                    },
                    {
                        "source": str(pkg3),
                        "pkg": {"planned_path": str(pkg3), "action": PlanOutput.REJECT},
                        "icon": {"planned_path": None, "action": PlanOutput.SKIP},
                    },
                ]
                sfo_cache = {str(pkg1): SFO_GAME, str(pkg2): SFO_GAME, str(pkg3): SFO_GAME}
                _, stats = executor.run(results, sfo_cache)

            self.assertEqual(stats["skipped"], 2)

    def test_icon_not_extracted_when_pkg_rejected(self):
        executor, pkg_utils, formatter, sorter = self._make_executor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_dir = Path(tmp_dir) / "_error"
            pkg_path = Path(tmp_dir) / "a.pkg"
            pkg_path.write_text("x", encoding="utf-8")
            icon_path = Path(tmp_dir) / "icon.png"

            with patch.dict(os.environ, {"ERROR_DIR": str(error_dir)}, clear=False):
                results = [
                    {
                        "source": str(pkg_path),
                        "pkg": {"planned_path": str(pkg_path), "action": PlanOutput.REJECT},
                        "icon": {"planned_path": str(icon_path), "action": PlanOutput.ALLOW},
                    }
                ]
                sfo_cache = {str(pkg_path): SFO_GAME}
                executor.run(results, sfo_cache)

            pkg_utils.extract_pkg_icon.assert_not_called()


if __name__ == "__main__":
    unittest.main()
