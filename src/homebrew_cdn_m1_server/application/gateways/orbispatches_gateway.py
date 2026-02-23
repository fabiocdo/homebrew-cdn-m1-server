from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from http.client import HTTPResponse
from typing import ClassVar, cast, final, override

from homebrew_cdn_m1_server.domain.protocols.title_metadata_lookup_protocol import (
    TitleMetadataLookupProtocol,
)


@final
class OrbisPatchesGateway(TitleMetadataLookupProtocol):
    _TITLE_ID_RE: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Z0-9]{9}$")
    _PUBLISHER_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"<strong[^>]*>\s*Publisher(?!\s*ID)\b(?:\s*<small.*?</small>)?\s*</strong>\s*(?P<publisher>.*?)\s*</li>",
        re.IGNORECASE | re.DOTALL,
    )
    _TAG_RE: ClassVar[re.Pattern[str]] = re.compile(r"<[^>]+>")
    _SPACE_RE: ClassVar[re.Pattern[str]] = re.compile(r"\s+")

    def __init__(
        self,
        base_url: str = "https://orbispatches.com",
        timeout_seconds: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._cache: dict[str, str | None] = {}

    @classmethod
    def _normalize_title_id(cls, title_id: str) -> str:
        normalized = str(title_id or "").strip().upper()
        if not cls._TITLE_ID_RE.match(normalized):
            return ""
        return normalized

    @classmethod
    def _extract_field(cls, payload: str, pattern: re.Pattern[str], group_name: str) -> str | None:
        match = pattern.search(payload)
        if match is None:
            return None

        body = match.group(group_name)
        without_tags = cls._TAG_RE.sub(" ", body)
        plain = html.unescape(without_tags)
        compact = cls._SPACE_RE.sub(" ", plain).strip()
        return compact or None

    @classmethod
    def _extract_publisher(cls, payload: str) -> str | None:
        return cls._extract_field(payload, cls._PUBLISHER_RE, "publisher")

    def _lookup_cached_publisher(self, title_id: str) -> str | None:
        key = self._normalize_title_id(title_id)
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]

        safe_key = urllib.parse.quote(key, safe="")
        request = urllib.request.Request(
            f"{self._base_url}/{safe_key}",
            headers={"User-Agent": "homebrew-cdn-m1-server/0.3"},
        )

        try:
            response_obj = cast(
                HTTPResponse,
                urllib.request.urlopen(request, timeout=self._timeout_seconds),
            )
            with response_obj as response:
                if int(response.status) >= 400:
                    self._cache[key] = None
                    return self._cache[key]
                payload = response.read().decode("utf-8", errors="ignore")
        except Exception:
            self._cache[key] = None
            return self._cache[key]

        publisher = self._extract_publisher(payload)
        self._cache[key] = publisher
        return self._cache[key]

    @override
    def lookup_by_title_id(self, title_id: str) -> str | None:
        return self._lookup_cached_publisher(title_id)
