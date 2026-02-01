

from pathlib import Path

from src.modules.auto_sorter import AutoSorter
from src import settings


def start():
    pkg_path = settings.PKG_DIR / "1.pkg"
    category = "ac"
    sorter = AutoSorter()
    print(f"--- Dry Run Test ---")
    planned = sorter.run(pkg_path, category)
    print(f"Planned destination: {planned}")

if __name__ == "__main__":
    start()
