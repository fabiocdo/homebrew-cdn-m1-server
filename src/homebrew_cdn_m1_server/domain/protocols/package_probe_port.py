from __future__ import annotations

from pathlib import Path
from typing import Protocol

from homebrew_cdn_m1_server.application.dto.probe_result import ProbeResult


class PackageProbePort(Protocol):
    def probe(self, pkg_path: Path) -> ProbeResult: ...
