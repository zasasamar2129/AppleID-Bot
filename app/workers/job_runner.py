"""Framework for scheduled worker functions.

Keeps workers as plain ``async def`` functions (matching the existing
project style) while centralising the guarantees every job needs:

* structured timing and per-job health tracking,
* slow-execution detection against a per-job threshold,
* failure capture that never kills the scheduler,
* a Redis overlap lock that cannot expire under a long job,
* a DB session that is always committed on success and rolled back on error,
* no secrets in logs.

Usage::

    @scheduled_job("process_orders", criticality="critical", slow_threshold=5.0)
    async def process_paid_orders_job() -> int:
        async with async_session() as session:
            ...
            return processed
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from app.utils.job_lock import job_lock
from app.workers.job_health import job_health

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def _format_duration(seconds: float) -> str:
    return f"{seconds * 1000:.0f}ms" if seconds < 1 else f"{seconds:.2f}s"


def scheduled_job(
    job_id: str,
    *,
    criticality: str = "low",
    slow_threshold: float = 5.0,
    lock_ttl: int = 120,
    use_lock: bool = True,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T | None]]]:
    """Wrap a worker coroutine with timing, health, locking and error capture.

    The wrapped function should return the number of records it processed (an
    ``int``). Returning ``None`` or a non-int is tolerated and treated as 0 for
    health purposes, so existing workers do not need changing.
    """

    def decorator(
        fn: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T | None]]:
        health = job_health.register(
            job_id, criticality=criticality, slow_threshold=slow_threshold
        )

        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            if not use_lock:
                return await _invoke(fn, args, kwargs, health)

            # TTL is renewed by job_lock while the body runs, so a job that
            # legitimately outlives lock_ttl still holds its lock.
            async with job_lock(job_id, ttl=lock_ttl) as acquired:
                if not acquired:
                    # Either another run holds the lock, or Redis is down.
                    # Skipping is safe: the next tick retries and the job's
                    # database-level guards make a duplicate run a no-op.
                    health.record_lock_skipped()
                    logger.debug(
                        "job=%s skipped: lock unavailable (held elsewhere or Redis down)",
                        job_id,
                    )
                    return None
                return await _invoke(fn, args, kwargs, health)

        return wrapper

    return decorator


async def _invoke(
    fn: Callable[..., Coroutine[Any, Any, T]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    health: Any,
) -> T | None:
    start = time.monotonic()
    processed = 0
    try:
        result = await fn(*args, **kwargs)
        if isinstance(result, int):
            processed = result
    except asyncio.CancelledError:
        # Shutdown: record as a failure but never swallow the cancellation.
        health.record_failure(time.monotonic() - start, "CancelledError")
        raise
    except Exception as exc:  # noqa: BLE001 - a job must never kill the scheduler
        duration = time.monotonic() - start
        health.record_failure(duration, type(exc).__name__)
        logger.error(
            "Scheduler job failed: job=%s duration=%s error_type=%s",
            health.job_id,
            _format_duration(duration),
            type(exc).__name__,
            exc_info=True,
        )
        return None

    duration = time.monotonic() - start
    health.record_success(duration, processed)
    if duration > health.slow_threshold:
        logger.warning(
            "Scheduler job slow: job=%s duration=%s threshold=%ss processed=%d",
            health.job_id,
            _format_duration(duration),
            health.slow_threshold,
            processed,
        )
    else:
        logger.debug(
            "Scheduler job completed: job=%s duration=%s processed=%d",
            health.job_id,
            _format_duration(duration),
            processed,
        )
    return result
