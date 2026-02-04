from __future__ import annotations

from src.models.globals import GlobalEnvs, GlobalFiles, GlobalPaths

def welcome():
    print("Welcome!")

def init_directories():
    paths = GlobalPaths()
    for p in vars(paths).values():
        p.mkdir(parents=True, exist_ok=True)

def start():
    welcome()
    init_directories()


if __name__ == "__main__":
    start()
