import subprocess
from pathlib import Path

from hb_store_m1.models.globals import Global


class PKGTool:
    @staticmethod
    def _run_pkgtool(command: str, *args: str):
        return subprocess.run(
            [Global.FILES.PKGTOOL_FILE_PATH, command, *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
            env={"DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1"},
            timeout=120,
        )

    @staticmethod
    def list_pkg_entries(pkg: Path):
        return PKGTool._run_pkgtool("pkg_listentries", str(pkg))

    @staticmethod
    def extract_pkg_entry(pkg: Path, entry_index: str, output_file: str):
        return PKGTool._run_pkgtool(
            "pkg_extractentry", str(pkg), entry_index, output_file
        )

    @staticmethod
    def list_sfo_entries(sfo_path: Path):
        return PKGTool._run_pkgtool("sfo_listentries", str(sfo_path))

    @staticmethod
    def validate_pkg(pkg: Path):
        return PKGTool._run_pkgtool("pkg_validate", str(pkg))


PKGTool = PKGTool()
