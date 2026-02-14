import runpy
import sys
import types

from hb_store_m1 import main as main_module


def test_given_welcome_when_called_then_prints_banner_and_table(monkeypatch):
    printed = []
    monkeypatch.setattr("builtins.print", lambda msg: printed.append(str(msg)))
    monkeypatch.setattr(main_module, "tabulate", lambda rows, tablefmt: f"{tablefmt}:{len(rows)}")
    monkeypatch.setattr(main_module.Globals.ENVS, "LOG_LEVEL", ["debug", "info"], raising=False)

    main_module.welcome()

    assert len(printed) == 2
    assert "v" in printed[0]
    assert any("fancy_outline:10" in line for line in printed)


def test_given_watcher_enabled_when_main_then_starts_watcher(monkeypatch):
    called = {"welcome": 0, "init": 0, "api": 0, "start": 0}
    monkeypatch.setattr(main_module, "welcome", lambda: called.__setitem__("welcome", 1))
    monkeypatch.setattr(
        main_module.InitUtils, "init_all", lambda: called.__setitem__("init", 1)
    )
    monkeypatch.setattr(
        main_module, "ensure_http_api_started", lambda: called.__setitem__("api", 1)
    )
    monkeypatch.setattr(
        main_module.Globals.ENVS, "WATCHER_ENABLED", True, raising=False
    )

    class _Watcher:
        def start(self):
            called["start"] += 1

    monkeypatch.setattr(main_module, "Watcher", _Watcher)

    main_module.main()

    assert called == {"welcome": 1, "init": 1, "api": 1, "start": 1}


def test_given_watcher_disabled_when_main_then_logs_info(monkeypatch):
    called = {"welcome": 0, "init": 0, "api": 0, "log": 0}
    monkeypatch.setattr(main_module, "welcome", lambda: called.__setitem__("welcome", 1))
    monkeypatch.setattr(
        main_module.InitUtils, "init_all", lambda: called.__setitem__("init", 1)
    )
    monkeypatch.setattr(
        main_module, "ensure_http_api_started", lambda: called.__setitem__("api", 1)
    )
    monkeypatch.setattr(
        main_module.Globals.ENVS, "WATCHER_ENABLED", False, raising=False
    )

    class _Log:
        def __init__(self, _module):
            pass

        def log_info(self, _message):
            called["log"] += 1

    monkeypatch.setattr(main_module, "LogUtils", _Log)

    main_module.main()

    assert called == {"welcome": 1, "init": 1, "api": 1, "log": 1}


def test_given_module_execution_when_run_main_dunder_then_calls_main(monkeypatch):
    fake_main = types.ModuleType("hb_store_m1.main")
    called = {"main": 0}

    def _main():
        called["main"] += 1

    fake_main.main = _main
    monkeypatch.setitem(sys.modules, "hb_store_m1.main", fake_main)

    runpy.run_module("hb_store_m1.__main__", run_name="__main__")

    assert called["main"] == 1
