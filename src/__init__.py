from __future__ import annotations

import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
argv = sys.argv[1:]
env = ""
for i, arg in enumerate(argv):
    if arg.startswith("--settings-env=") or arg.startswith("-E="):
        env = arg.split("=", 1)[1].strip()
        break
    if arg in {"--settings-env", "-E"} and i + 1 < len(argv):
        env = argv[i + 1].strip()
        break

path = root / (f"settings-{env}.env" if env else "settings.env")
if env:
    if env.endswith(".env"):
        config_name = env
    elif env.startswith("settings-"):
        config_name = f"{env}.env"
    else:
        config_name = f"settings-{env}.env"
    path = root / config_name
if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

data_dir = pathlib.Path("/data")
os.environ["DATA_DIR"] = str(data_dir)
os.environ.setdefault("STORE_DIR", str(data_dir))
os.environ.setdefault("STORE_DIR", str(data_dir))
os.environ.setdefault("INDEX_DIR", str(data_dir))
os.environ.setdefault("PKG_DIR", str(data_dir / "pkg"))
os.environ.setdefault("ERROR_DIR", str(data_dir / "_error"))
os.environ.setdefault("CACHE_DIR", str(data_dir / "_cache"))
os.environ.setdefault("LOG_DIR", str(data_dir / "_logs"))
os.environ.setdefault("MEDIA_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "_media"))
os.environ.setdefault("GAME_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "game"))
os.environ.setdefault("DLC_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "dlc"))
os.environ.setdefault("UPDATE_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "update"))
os.environ.setdefault("SAVE_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "save"))
os.environ.setdefault("UNKNOWN_DIR", str(pathlib.Path(os.environ["PKG_DIR"]) / "_unknown"))
os.environ.setdefault("PKGTOOL_PATH", "/app/bin/pkgtool")
os.environ.setdefault("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "1")
