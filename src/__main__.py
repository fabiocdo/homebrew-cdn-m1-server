

from pathlib import Path

from src.modules import AutoFormatter
from src.modules.auto_sorter import AutoSorter


def start():
    formatter = AutoFormatter()
    sorter = AutoSorter()
    SFO_DLC = {
        "title": "The Frozen Wilds",
        "title_id": "CUSA01021",
        "app_type": "addon",
        "region": "US",
        "version": "01.00",
        "category": "ac",
        "content_id": "UP9000-CUSA01021_00-DLC0000000000001"
    }
    pkg_path = Path("/home/fabio/dev/homebrew-store-cdn/data/pkg/1.pkg")
    # print(sorter.dry_run(pkg_path, "ac"))
    # sorter.run(pkg_path, "ac")
    print(formatter.dry_run(pkg_path, SFO_DLC))
    # formatter.run(pkg_path, SFO_DLC)

if __name__ == "__main__":
    start()
