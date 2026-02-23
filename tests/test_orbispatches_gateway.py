from __future__ import annotations

from collections.abc import Callable
import urllib.request
from typing import cast

import pytest

from homebrew_cdn_m1_server.application.gateways.orbispatches_gateway import (
    OrbisPatchesGateway,
)


class _FakeResponse:
    def __init__(self, payload: str, status: int = 200) -> None:
        self.status: int = status
        self._payload: bytes = payload.encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object,
    ) -> None:
        return None


def test_orbispatches_gateway_given_title_html_when_lookup_then_returns_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = """
    <li class="bd-links-group py-2">
      <strong class="bd-links-heading d-flex w-100 align-items-center fw-semibold">
        Publisher<small class="ms-2 fw-normal"><a href="/UP4433">View</a></small>
      </strong>
      Mojang
    </li>
    <li class="bd-links-group py-2">
      <strong class="bd-links-heading d-flex w-100 align-items-center fw-semibold">
        Publisher ID
      </strong>
      UP4433
    </li>
    """
    gateway = OrbisPatchesGateway()

    def _fake_urlopen(_request: object, timeout: object | None = None) -> _FakeResponse:
        _ = timeout
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", cast(Callable[..., object], _fake_urlopen))

    assert gateway.lookup_by_title_id("CUSA00744") == "Mojang"


def test_orbispatches_gateway_given_same_title_id_when_lookup_twice_then_uses_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = OrbisPatchesGateway()
    calls: list[str] = []

    def _fake_urlopen(request: object, timeout: object | None = None) -> _FakeResponse:
        calls.append(str(timeout))
        _ = request
        return _FakeResponse(
            """
            <strong>Publisher</strong>
            Mojang
            </li>
            """
        )

    monkeypatch.setattr(urllib.request, "urlopen", cast(Callable[..., object], _fake_urlopen))

    first = gateway.lookup_by_title_id("cusa00744")
    second = gateway.lookup_by_title_id("CUSA00744")

    assert first == "Mojang"
    assert second == "Mojang"
    assert len(calls) == 1


def test_orbispatches_gateway_given_invalid_title_id_when_lookup_then_returns_none() -> None:
    gateway = OrbisPatchesGateway()
    assert gateway.lookup_by_title_id("not_a_title_id") is None
