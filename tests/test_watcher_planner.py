import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.modules.helpers.watcher_planner import WatcherPlanner
from src.modules.auto_formatter import AutoFormatter
from src.modules.auto_sorter import AutoSorter
from src.models.watcher_models import PlanOutput


class TestWatcherPlanner(unittest.TestCase):
    def _make_planner(self):
        pkg_utils = MagicMock()
        formatter = MagicMock(spec=AutoFormatter)
        sorter = MagicMock(spec=AutoSorter)
        return WatcherPlanner(pkg_utils, formatter, sorter), pkg_utils, formatter, sorter

    def test_plan_no_changes(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        with patch.dict(os.environ, {"PKG_DIR": "/tmp"}, clear=False):
            with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=([], False)):
                results, sfo_cache = planner.plan()

        self.assertEqual(results, [])
        self.assertEqual(sfo_cache, {})
        pkg_utils.extract_pkg_icon.assert_not_called()
        formatter.dry_run.assert_not_called()
        sorter.dry_run.assert_not_called()

    def test_plan_missing_sfo(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                scan_results = [(pkg_path, None)]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, sfo_cache = planner.plan()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "missing_sfo")
        self.assertEqual(results[0]["icon"]["action"], PlanOutput.REJECT)
        self.assertEqual(sfo_cache, {})

    def test_plan_invalid_formatter(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.INVALID, "bad.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))
        pkg_utils.extract_pkg_icon.return_value = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                sfo_data = {"content_id": ""}
                scan_results = [(pkg_path, sfo_data)]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "formatter_invalid")

    def test_plan_formatter_conflict(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.CONFLICT, "conflict.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))
        pkg_utils.extract_pkg_icon.return_value = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                scan_results = [(pkg_path, {"content_id": ""})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "formatter_conflict")

    def test_plan_sorter_conflict(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.OK, "ok.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.CONFLICT, Path("/tmp"))
        pkg_utils.extract_pkg_icon.return_value = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                scan_results = [(pkg_path, {"content_id": ""})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "sorter_conflict")

    def test_plan_planned_path_conflict(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.OK, "same.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))
        pkg_utils.extract_pkg_icon.return_value = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg1 = Path(tmp_dir) / "a.pkg"
                pkg2 = Path(tmp_dir) / "b.pkg"
                pkg1.touch()
                pkg2.touch()
                scan_results = [(pkg1, {"content_id": ""}), (pkg2, {"content_id": ""})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[1]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[1]["pkg"]["reason"], "planned_path_conflict")

    def test_plan_skip_when_already_in_place(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.SKIP, "same.pkg")
        pkg_utils.extract_pkg_icon.return_value = Path("/tmp/icon.png")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "same.pkg"
                pkg_path.touch()
                sorter.dry_run.return_value = (AutoSorter.PlanResult.SKIP, pkg_path.parent)
                scan_results = [(pkg_path, {"content_id": "CID1"})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.SKIP)

    def test_plan_missing_icon_rejects(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.OK, "ok.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))
        pkg_utils.extract_pkg_icon.return_value = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                scan_results = [(pkg_path, {"content_id": "CID1"})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "missing_icon")

    def test_plan_invalid_icon_rejects(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.OK, "ok.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))
        pkg_utils.is_valid_png.return_value = False

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg_path = Path(tmp_dir) / "a.pkg"
                pkg_path.touch()
                icon_path = Path(tmp_dir) / "icon.png"
                icon_path.touch()
                pkg_utils.extract_pkg_icon.return_value = icon_path
                scan_results = [(pkg_path, {"content_id": "CID1"})]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["pkg"]["action"], PlanOutput.REJECT)
        self.assertEqual(results[0]["pkg"]["reason"], "invalid_icon")

    def test_plan_icon_actions(self):
        planner, pkg_utils, formatter, sorter = self._make_planner()
        formatter.dry_run.return_value = (AutoFormatter.PlanResult.OK, "ok.pkg")
        sorter.dry_run.return_value = (AutoSorter.PlanResult.OK, Path("/tmp"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"PKG_DIR": tmp_dir}, clear=False):
                pkg1 = Path(tmp_dir) / "a.pkg"
                pkg2 = Path(tmp_dir) / "b.pkg"
                pkg3 = Path(tmp_dir) / "c.pkg"
                pkg1.touch()
                pkg2.touch()
                pkg3.touch()

                icon1 = Path(tmp_dir) / "icon1.png"
                icon2 = Path(tmp_dir) / "icon2.png"
                icon2.touch()

                pkg_utils.extract_pkg_icon.side_effect = [icon1, icon2, icon1]
                scan_results = [
                    (pkg1, {"content_id": "CID1"}),
                    (pkg2, {"content_id": "CID2"}),
                    (pkg3, {"content_id": "CID3"}),
                ]
                with patch("src.modules.helpers.watcher_planner.scan_pkgs", return_value=(scan_results, True)):
                    results, _ = planner.plan()

        self.assertEqual(results[0]["icon"]["action"], PlanOutput.ALLOW)
        self.assertEqual(results[1]["icon"]["action"], PlanOutput.SKIP)
        self.assertEqual(results[2]["icon"]["action"], PlanOutput.REJECT)


if __name__ == "__main__":
    unittest.main()
