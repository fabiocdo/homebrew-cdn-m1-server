from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget


class UserSettings(BaseModel):
    server_ip: str = Field(default="127.0.0.1")
    server_port: int = Field(default=80, ge=1, le=65535)
    enable_tls: bool = Field(default=False)
    log_level: str = Field(default="info")
    reconcile_pkg_preprocess_workers: int = Field(default=1, ge=1)
    reconcile_cron_expression: str = Field(default="")
    output_targets: tuple[OutputTarget, ...] = Field(
        default=(OutputTarget.HB_STORE, OutputTarget.FPKGI)
    )
    pkgtool_timeout_seconds: int = Field(default=300, ge=1)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"debug", "info", "warn", "warning", "error"}:
            raise ValueError("LOG_LEVEL must be one of: debug, info, warn, error")
        return "warning" if normalized == "warn" else normalized
