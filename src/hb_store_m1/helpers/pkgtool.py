import math
import subprocess
from pathlib import Path

from hb_store_m1.models.globals import Globals


class PKGTool:
    @staticmethod
    def _run_pkgtool(command: str, *args: str, timeout_seconds: int | None = None):
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else int(Globals.ENVS.PKGTOOL_TIMEOUT_SECONDS)
        )
        timeout = max(1, int(timeout))
        return subprocess.run(
            [Globals.FILES.PKGTOOL_FILE_PATH, command, *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
            env={"DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1"},
            timeout=timeout,
        )

    @staticmethod
    def _validate_timeout_seconds(pkg: Path) -> int:
        base_timeout = max(1, int(Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_SECONDS))
        per_gb_timeout = max(
            1,
            int(Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_PER_GB_SECONDS),
        )
        max_timeout = int(Globals.ENVS.PKGTOOL_VALIDATE_TIMEOUT_MAX_SECONDS)

        try:
            pkg_size_bytes = max(0, int(pkg.stat().st_size))
        except OSError:
            return base_timeout

        size_gb = max(1, math.ceil(pkg_size_bytes / (1024**3)))
        scaled_timeout = size_gb * per_gb_timeout
        timeout = max(base_timeout, scaled_timeout)

        if max_timeout > 0:
            timeout = min(timeout, max_timeout)

        return timeout

    @staticmethod
    def list_pkg_entries(pkg: Path):
        return PKGTool._run_pkgtool("pkg_listentries", str(pkg))

    @staticmethod
    def extract_pkg_entry(pkg: Path, entry_index: str, output_file: str):
        return PKGTool._run_pkgtool(
            "pkg_extractentry", str(pkg), entry_index, output_file
        )

    @staticmethod
    def list_sfo_entries(sfo: Path):
        return PKGTool._run_pkgtool("sfo_listentries", str(sfo))

    @staticmethod
    def validate_pkg(pkg: Path):
        return PKGTool._run_pkgtool(
            "pkg_validate",
            str(pkg),
            timeout_seconds=PKGTool._validate_timeout_seconds(pkg),
        )


PKGTool = PKGTool()
