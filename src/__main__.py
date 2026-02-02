from __future__ import annotations

import os
import re
from pathlib import Path
from src.modules import Watcher
from src.utils.models.log_models import MODULE_COLORS


def _read_toml_value(path: Path, key: str) -> str | None:
    """
    Read a simple key from a TOML file without dependencies.

    :param path: Path to the TOML file
    :param key: Key to search for
    :return: String value if found, otherwise None
    """
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith(f"{key}"):
            continue
        parts = stripped.split("=", 1)
        if len(parts) < 2:
            continue
        value = parts[1].split("#", 1)[0].strip()
        if len(value) >= 2 and (
            (value.startswith("\"") and value.endswith("\""))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        elif value.startswith("\"") or value.startswith("'"):
            value = value[1:]
        return value.strip()
    return None


def _print_startup_info() -> None:
    """
    Print startup configuration summary as a boxed table.

    :param: None
    :return: None
    """
    root = Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    name = _read_toml_value(pyproject, "name") or "homebrew-store-cdn"
    version = _read_toml_value(pyproject, "version")

    title = f"{name} v{version}" if version else name
    reset = MODULE_COLORS.get("RESET", "")
    color_map = {
        "WATCHER": MODULE_COLORS.get("WATCHER", ""),
        "AUTO_INDEXER": MODULE_COLORS.get("AUTO_INDEXER", ""),
        "AUTO_FORMATTER": MODULE_COLORS.get("AUTO_FORMATTER", ""),
    }

    entries = [
        ("", "", None),
        ("BASE_URL", os.environ.get("BASE_URL", ""), None),
        ("LOG_LEVEL", os.environ.get("LOG_LEVEL", ""), None),
        ("", "", None),
        ("WATCHER_ENABLED", os.environ.get("WATCHER_ENABLED", ""), "WATCHER"),
        ("WATCHER_PERIODIC_SCAN_SECONDS", os.environ.get("WATCHER_PERIODIC_SCAN_SECONDS", ""), "WATCHER"),
        ("WATCHER_ACCESS_LOG_TAIL", os.environ.get("WATCHER_ACCESS_LOG_TAIL", ""), "WATCHER"),
        ("WATCHER_ACCESS_LOG_INTERVAL", os.environ.get("WATCHER_ACCESS_LOG_INTERVAL", ""), "WATCHER"),
        ("", "", None),
        ("AUTO_INDEXER_OUTPUT_FORMAT", os.environ.get("AUTO_INDEXER_OUTPUT_FORMAT", ""), "AUTO_INDEXER"),
        ("", "", None),
        ("AUTO_FORMATTER_TEMPLATE", os.environ.get("AUTO_FORMATTER_TEMPLATE", ""), "AUTO_FORMATTER"),
        ("AUTO_FORMATTER_MODE", os.environ.get("AUTO_FORMATTER_MODE", ""), "AUTO_FORMATTER"),
        ("", "", None),
    ]

    key_width = max(len(key) for key, _value, _color in entries if key)

    plain_lines: list[str] = [title.upper()]
    colored_lines: list[str] = [title.upper()]

    for key, value, group in entries:
        if not key:
            plain_lines.append("")
            colored_lines.append("")
            continue
        val = (value or "").upper()
        padding = " " * (key_width - len(key) + 2)
        plain = f"{key}{padding}{val}"
        if group and color_map.get(group):
            color = color_map[group]
            colored = f"{color}{key}{reset}{padding}{color}{val}{reset}"
        else:
            colored = plain
        plain_lines.append(plain)
        colored_lines.append(colored)

    def _strip_ansi(text: str) -> str:
        return re.sub(r"\x1B\[[0-9;]*m", "", text)

    max_len = max(len(line) for line in plain_lines)
    border = "=" * (max_len + 6)
    print(border)
    for line in colored_lines:
        visible = _strip_ansi(line)
        pad = " " * (max_len - len(visible))
        print(f"|| {line}{pad} ||")
    print(border)

if __name__ == "__main__":
    _print_startup_info()
    Watcher().start()
