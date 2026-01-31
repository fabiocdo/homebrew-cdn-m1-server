import subprocess
from pathlib import Path


def _ensure_binary():
    tools_dir = Path(__file__).resolve().parent
    source = tools_dir / "lib" / "sfotool.c"
    binary = tools_dir / "bin" / "sfotool"

    if binary.is_file():
        return binary
    if not source.is_file():
        return None
    try:
        binary.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["cc", str(source), "-o", str(binary)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return binary
    except Exception:
        return None


def extract_sfo_data(pkg_path):
    binary = _ensure_binary()
    if binary is None:
        return {}
    try:
        output = subprocess.check_output([str(binary), str(pkg_path)], text=True)
    except Exception:
        return {}

    data = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data
