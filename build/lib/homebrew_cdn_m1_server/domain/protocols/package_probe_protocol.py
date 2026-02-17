from __future__ import annotations

from pathlib import Path
from typing import Protocol

from homebrew_cdn_m1_server.domain.models.results import ProbeResult


class PackageProbeProtocol(Protocol):
    def probe(self, pkg_path: Path) -> ProbeResult: ...
