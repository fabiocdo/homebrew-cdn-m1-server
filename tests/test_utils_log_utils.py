from hb_store_m1.models.log import LogLevel, LogModule
from hb_store_m1.utils import log_utils


def test_given_debug_level_when_log_debug_then_prints_message(monkeypatch):
    messages = []

    def fake_print(message):
        messages.append(message)

    monkeypatch.setattr(log_utils, "CURRENT_LOG_PRIORITY", LogLevel.DEBUG.priority())
    monkeypatch.setattr("builtins.print", fake_print)

    log = log_utils.LogUtils(LogModule.PKG_UTIL)
    log.log_debug("hello")

    assert any("hello" in msg for msg in messages)


def test_given_error_level_when_log_debug_then_skips_print(monkeypatch):
    messages = []

    def fake_print(message):
        messages.append(message)

    monkeypatch.setattr(log_utils, "CURRENT_LOG_PRIORITY", LogLevel.ERROR.priority())
    monkeypatch.setattr("builtins.print", fake_print)

    log = log_utils.LogUtils(LogModule.PKG_UTIL)
    log.log_debug("hidden")

    assert messages == []
