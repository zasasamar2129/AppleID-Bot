"""Per-job scheduler health tracking.

Lightweight in-process registry so scheduler performance is observable without
a metrics stack. Only non-sensitive counters and error *type names* are kept —
never job arguments, payloads, or exception messages that could contain user
data or secrets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class JobHealth:
    job_id: str
    criticality: str = "low"
    slow_threshold: float = 5.0
    last_started: float | None = None
    last_duration: float | None = None
    last_finished: float | None = None
    last_status: str = "never_run"
    last_error_type: str | None = None
    consecutive_failures: int = 0
    total_runs: int = 0
    total_failures: int = 0
    total_misfires: int = 0
    last_processed: int = 0
    skipped_locked: int = 0
    _recent: list[float] = field(default_factory=list, repr=False)

    def record_success(self, duration: float, processed: int) -> None:
        now = time.monotonic()
        self.last_started = now
        self.last_finished = now
        self.last_duration = duration
        self.last_status = "ok"
        self.last_error_type = None
        self.last_processed = processed
        self.consecutive_failures = 0
        self.total_runs += 1
        self._recent.append(duration)
        del self._recent[:-20]

    def record_failure(self, duration: float, error_type: str) -> None:
        now = time.monotonic()
        self.last_started = now
        self.last_finished = now
        self.last_duration = duration
        self.last_status = "failed"
        self.last_error_type = error_type
        self.consecutive_failures += 1
        self.total_runs += 1
        self.total_failures += 1
        self._recent.append(duration)
        del self._recent[:-20]

    def record_misfire(self, delay: float) -> None:
        self.total_misfires += 1
        self.last_status = "misfired"

    def record_lock_skipped(self) -> None:
        self.skipped_locked += 1

    @property
    def seconds_since_last_run(self) -> float | None:
        if self.last_finished is None:
            return None
        return time.monotonic() - self.last_finished

    @property
    def avg_duration(self) -> float | None:
        if not self._recent:
            return None
        return sum(self._recent) / len(self._recent)

    def is_healthy(self) -> bool:
        if self.consecutive_failures >= 3:
            return False
        return self.last_status in ("ok", "never_run", "misfired")

    def snapshot(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "criticality": self.criticality,
            "last_status": self.last_status,
            "last_duration_s": round(self.last_duration, 3) if self.last_duration else None,
            "avg_duration_s": round(self.avg_duration, 3) if self.avg_duration else None,
            "last_error_type": self.last_error_type,
            "consecutive_failures": self.consecutive_failures,
            "total_runs": self.total_runs,
            "total_failures": self.total_failures,
            "total_misfires": self.total_misfires,
            "last_processed": self.last_processed,
            "skipped_locked": self.skipped_locked,
            "seconds_since_last_run": (
                round(self.seconds_since_last_run, 1)
                if self.seconds_since_last_run is not None
                else None
            ),
        }


class JobHealthRegistry:
    """Process-wide registry of job health records."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobHealth] = {}

    def register(
        self, job_id: str, criticality: str = "low", slow_threshold: float = 5.0
    ) -> JobHealth:
        health = self._jobs.get(job_id)
        if health is None:
            health = JobHealth(
                job_id=job_id,
                criticality=criticality,
                slow_threshold=slow_threshold,
            )
            self._jobs[job_id] = health
        return health

    def get(self, job_id: str) -> JobHealth | None:
        return self._jobs.get(job_id)

    def all(self) -> list[JobHealth]:
        return list(self._jobs.values())

    def reset(self) -> None:
        self._jobs.clear()


job_health = JobHealthRegistry()


def format_health_report() -> str:
    """Render a human-readable health report (no secrets, no payloads)."""
    jobs = sorted(job_health.all(), key=lambda j: j.job_id)
    if not jobs:
        return "No scheduler jobs registered."

    lines = ["Scheduler health:"]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines.append(f"generated_at={now}")
    for job in jobs:
        age = job.seconds_since_last_run
        lines.append(
            f"  job={job.job_id} criticality={job.criticality} "
            f"status={job.last_status} "
            f"last_duration_s={round(job.last_duration, 3) if job.last_duration else 'n/a'} "
            f"age_s={round(age, 1) if age is not None else 'n/a'} "
            f"failures={job.consecutive_failures} "
            f"misfires={job.total_misfires} "
            f"processed={job.last_processed}"
        )
    return "\n".join(lines)
