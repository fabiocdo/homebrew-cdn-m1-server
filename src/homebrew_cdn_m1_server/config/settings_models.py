from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from homebrew_cdn_m1_server.domain.models.output_target import OutputTarget


class UserSettings(BaseModel):
    server_ip: str | None = Field(default=None)
    server_port: int | None = Field(default=None, ge=1, le=65535)
    enable_tls: bool | None = Field(default=None)
    log_level: str | None = Field(default=None)
    reconcile_pkg_preprocess_workers: int | None = Field(default=None, ge=1)
    reconcile_cron_expression: str | None = Field(default=None)
    output_targets: tuple[OutputTarget, ...] | None = Field(default=None)
    pkgtool_timeout_seconds: int | None = Field(default=None, ge=1)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        if normalized not in {"debug", "info", "warn", "warning", "error"}:
            raise ValueError("LOG_LEVEL must be one of: debug, info, warn, error")
        return "warning" if normalized == "warn" else normalized
