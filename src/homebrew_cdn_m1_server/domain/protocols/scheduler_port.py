from __future__ import annotations

from typing import Callable, Protocol


class SchedulerPort(Protocol):
    def schedule_interval(
        self, job_id: str, seconds: int, func: Callable[[], object]
    ) -> None: ...

    def schedule_cron(
        self, job_id: str, cron_expression: str, func: Callable[[], object]
    ) -> None: ...

    def start(self) -> None: ...

    def shutdown(self) -> None: ...
