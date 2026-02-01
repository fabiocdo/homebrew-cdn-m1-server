import os
from pathlib import Path
from enum import Enum
from src.utils import log


class AutoFormatter:
    """
    AutoFormatter handles PKG renaming based on PARAM.SFO metadata.

    It supports dry-run planning and real renaming using a user-defined
    template and formatting mode.
    """

    class PlanResult(Enum):
        """Enumeration of dry-run planning results."""
        OK = "ok"
        SKIP = "skip"
        CONFLICT = "conflict"
        NOT_FOUND = "not_found"
        INVALID = "invalid"

    def __init__(self):
        """
        Initialize the formatter.
        """
        pass

    class _SafeDict(dict):
        """Dictionary that returns empty string for missing keys."""

        def __missing__(self, key):
            return ""

    def dry_run(self, pkg: Path, sfo_data: dict) -> tuple[PlanResult, str | None]:
        """
        Plan the final PKG filename and check for conflicts.

        :param pkg: Path object representing the source PKG file
        :param sfo_data: Parsed PARAM.SFO data
        :return: Tuple of (PlanResult, Planned filename or current name)
        """
        if not pkg.exists():
            return self.PlanResult.NOT_FOUND, pkg.name

        safe_data = {
            key: self._normalize_value(key, value)
            for key, value in (sfo_data or {}).items()
        }

        template = os.environ["AUTO_FORMATTER_TEMPLATE"]
        planned_name = template.format_map(self._SafeDict(safe_data)).strip()
        planned_name = self._sanitize_filename(planned_name)

        if not planned_name:
            return self.PlanResult.INVALID, pkg.name

        if not planned_name.lower().endswith(".pkg"):
            planned_name = f"{planned_name}.pkg"

        if pkg.name == planned_name:
            return self.PlanResult.SKIP, planned_name

        target_path = pkg.with_name(planned_name)
        if target_path.exists():
            return self.PlanResult.CONFLICT, planned_name

        return self.PlanResult.OK, planned_name

    def run(self, pkg: Path, sfo_data: dict) -> str | None:
        """
        Rename the PKG file using SFO metadata.

        :param pkg: Path object representing the PKG file
        :param sfo_data: Parsed PARAM.SFO data
        :return: New filename if renamed, otherwise None
        """
        plan_result, planned_name = self.dry_run(pkg, sfo_data)

        if plan_result == self.PlanResult.NOT_FOUND:
            log("error", "PKG file not found", message=f"{pkg}", module="AUTO_FORMATTER")
            return None

        if plan_result == self.PlanResult.INVALID:
            log("error", "Failed to generate filename from template", message=f"{pkg.name}", module="AUTO_FORMATTER")
            return None

        if plan_result == self.PlanResult.SKIP:
            log("debug", "Skipping rename. PKG is already renamed", message=f"{planned_name}", module="AUTO_FORMATTER")
            return None

        if plan_result == self.PlanResult.CONFLICT:
            log("error", "Failed to rename PKG. Target name already exists", message=f"{pkg.name} -> {planned_name}", module="AUTO_FORMATTER")
            error_dir = Path(
                os.getenv("ERROR_DIR", str(Path(os.getenv("DATA_DIR", "data")) / "_error"))
            )
            error_dir.mkdir(parents=True, exist_ok=True)
            conflict_path = error_dir / pkg.name
            counter = 1
            while conflict_path.exists():
                conflict_path = error_dir / f"{pkg.stem}_{counter}{pkg.suffix}"
                counter += 1
            pkg.rename(conflict_path)
            log("warn", "PKG moved to errors folder", message=f"{pkg.name} -> {conflict_path.name}", module="AUTO_FORMATTER")
            return None

        target_path = pkg.with_name(planned_name)
        pkg.rename(target_path)
        log("info", "PKG renamed successfully", message=f"{pkg.name} -> {planned_name}", module="AUTO_FORMATTER")
        return planned_name

    @staticmethod
    def _normalize_value(key: str, value):
        """
        Normalize SFO values according to key and formatter mode.

        :param key: SFO field name
        :param value: Raw SFO value
        :return: Normalized string value
        """
        if value is None:
            return ""

        value = str(value)

        if key.lower() == "title":
            mode = os.getenv("AUTO_FORMATTER_MODE", "none")
            if mode == "uppercase":
                return value.upper()
            if mode == "lowercase":
                return value.lower()
            if mode == "capitalize":
                import re
                roman_numerals = r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$"
                parts = []
                for part in value.split():
                    if re.match(roman_numerals, part.upper()):
                        parts.append(part.upper())
                    else:
                        parts.append(part.capitalize())
                return " ".join(parts)
            if mode == "snake_case":
                return "_".join(value.split())
            if mode == "snake_uppercase":
                return "_".join(value.split()).upper()
            if mode == "snake_lowercase":
                return "_".join(value.split()).lower()

        return value

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        Sanitize a filename by removing path separators and invalid characters.
        """
        invalid = '<>:"/\\|?*'
        table = str.maketrans({ch: "_" for ch in invalid})
        name = name.translate(table)
        name = name.replace("_ ", "_").replace(" _", "_")
        while "__" in name:
            name = name.replace("__", "_")
        return name.strip()
