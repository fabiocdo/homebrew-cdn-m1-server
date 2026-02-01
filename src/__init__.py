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

os.environ.setdefault("DATA_DIR", str(root / "data"))
data_dir = pathlib.Path(os.environ["DATA_DIR"])
pkg_dir = data_dir / "pkg"
os.environ.setdefault("PKG_DIR", str(pkg_dir))
os.environ.setdefault("GAME_DIR", str(pkg_dir / "game"))
os.environ.setdefault("DLC_DIR", str(pkg_dir / "dlc"))
os.environ.setdefault("UPDATE_DIR", str(pkg_dir / "update"))
os.environ.setdefault("SAVE_DIR", str(pkg_dir / "save"))
os.environ.setdefault("UNKNOWN_DIR", str(pkg_dir / "_unknown"))
os.environ.setdefault("MEDIA_DIR", str(data_dir / "_media"))
os.environ.setdefault("ERROR_DIR", str(data_dir / "_error"))
os.environ.setdefault("CACHE_DIR", str(data_dir / "_cache"))
os.environ.setdefault("STORE_DIR", str(data_dir))
os.environ.setdefault("INDEX_DIR", str(data_dir))
