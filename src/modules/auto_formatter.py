from pathlib import Path
from src.utils import log
from src import settings


class AutoFormatter:
    """
    AutoFormatter handles PKG renaming based on PARAM.SFO metadata.

    It supports dry-run planning and real renaming using a user-defined
    template and formatting mode.
    """

    def __init__(self, template: str | None = None, mode: str | None = None, error_path: str | Path | None = None):
        """
        Initialize the formatter.

        :param template: Filename template (e.g. "{title} {title_id} {app_type}")
        :param mode: Text mode for title normalization
                     ("uppercase", "lowercase", "capitalize", or None)
        :param error_path: Path where conflicting files will be moved
        """
        self.template = template or settings.AUTO_FORMATTER_TEMPLATE
        self.mode = mode or settings.AUTO_FORMATTER_MODE
        self.error_path = Path(error_path) if error_path else settings.ERROR_DIR

    class _SafeDict(dict):
        """Dictionary that returns empty string for missing keys."""

        def __missing__(self, key):
            return ""

    def _normalize_value(self, key: str, value):
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
            if self.mode == "uppercase":
                return value.upper()
            if self.mode == "lowercase":
                return value.lower()
            if self.mode == "capitalize":
                import re
                roman_numerals = r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$"
                parts = []
                for part in value.split():
                    if re.match(roman_numerals, part.upper()):
                        parts.append(part.upper())
                    else:
                        parts.append(part.capitalize())
                return " ".join(parts)

        return value

    def dry_run(self, pkg: Path, sfo_data: dict) -> str | None:
        """
        Plan the final PKG filename and check for conflicts.

        :param pkg: Path-like object representing the source PKG file
        :param sfo_data: Parsed PARAM.SFO data
        :return: Planned filename or None if conflict or not resolvable
        """
        safe_data = {
            key: self._normalize_value(key, value)
            for key, value in (sfo_data or {}).items()
        }

        planned_name = (
            self.template.format_map(self._SafeDict(safe_data)).strip()
        )

        if not planned_name:
            return None

        if not planned_name.lower().endswith(".pkg"):
            planned_name = f"{planned_name}.pkg"

        if pkg.name != planned_name:
            target_path = pkg.with_name(planned_name)
            if target_path.exists():
                log("error", "Failed to rename PKG", message=f"{pkg.name} -> {planned_name} (Target already exists)", module="AUTO_FORMATTER")
                return None

        return planned_name

    def run(self, pkg: Path, sfo_data: dict) -> str | None:
        """
        Rename the PKG file using SFO metadata.

        :param pkg: Path object representing the PKG file
        :param sfo_data: Parsed PARAM.SFO data
        :return: New filename if renamed, otherwise None
        """
        if not pkg.exists():
            log("error", "PKG file not found", message=f"{pkg}", module="AUTO_FORMATTER")
            return None

        planned_name = self.dry_run(pkg, sfo_data)

        if pkg.name == planned_name:
            log("info","Skipping rename",message=f"{planned_name} (PKG is already renamed)",module="AUTO_FORMATTER")
            return None

        try:
            target_path = pkg.with_name(planned_name)
            pkg.rename(target_path)

        except Exception:
            if self.error_path:
                try:
                    self.error_path.mkdir(parents=True, exist_ok=True)

                    conflict_path = self.error_path / pkg.name
                    counter = 1

                    while conflict_path.exists():
                        conflict_path = self.error_path / f"{pkg.stem}_{counter}{pkg.suffix}"
                        counter += 1

                    pkg.rename(conflict_path)

                    log("warn", "PKG moved to errors folder due to execution error", message=f"{pkg.name} -> {conflict_path.name}", module="AUTO_FORMATTER")

                except Exception as move_err:
                    log("error", "Failed to move PKG to errors folder", message=f"{pkg.name}: {str(move_err)}", module="AUTO_FORMATTER")

            return None

        return planned_name
