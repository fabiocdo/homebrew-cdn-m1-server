# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Callable, final, override

from apscheduler.schedulers.background import BackgroundScheduler

from homebrew_cdn_m1_server.domain.protocols.scheduler_protocol import SchedulerProtocol


@final
class APSchedulerRunner(SchedulerProtocol):
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    @staticmethod
    def _parse_cron(cron_expression: str) -> dict[str, str]:
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 fields")
        minute, hour, day, month, day_of_week = parts
        return {
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "day_of_week": day_of_week,
        }

    @override
    def schedule_interval(
        self, job_id: str, seconds: int, func: Callable[[], object]
    ) -> None:
        _ = self._scheduler.add_job(
            func,
            "interval",
            id=job_id,
            seconds=max(1, int(seconds)),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    @override
    def schedule_cron(
        self, job_id: str, cron_expression: str, func: Callable[[], object]
    ) -> None:
        cron_fields = self._parse_cron(cron_expression)
        _ = self._scheduler.add_job(
            func,
            "cron",
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            **cron_fields,
        )

    @override
    def start(self) -> None:
        self._scheduler.start()

    @override
    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
