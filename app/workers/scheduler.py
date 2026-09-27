from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from apscheduler.events import EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.utils.job_lock import SchedulerSingleton
from app.utils.loop_monitor import monitor_event_loop_lag
from app.workers.job_health import job_health

logger = logging.getLogger(__name__)

# Event-loop lag monitor cadence. A 1s tick with a 2s threshold is cheap: the
# monitor task does no I/O and holds no locks.
LOOP_MONITOR_INTERVAL = 1.0
LOOP_MONITOR_THRESHOLD = 2.0

_scheduler: AsyncIOScheduler | None = None
_singleton: SchedulerSingleton | None = None
_loop_monitor_stop: asyncio.Event | None = None

# Misfire policy, chosen per job from its semantics rather than applied blindly.
#
# misfire_grace_time: how long after its scheduled time a run may still start.
#   - This is a RECOVERY window, not a licence to be late. It is set to the
#     job's interval so a delayed run still executes exactly once, but the
#     underlying stalls are fixed separately (see EncryptionService key cache).
#   - cleanup: generous 120s; it is idempotent housekeeping and a late run is
#     harmless.
#   - process_orders: 120s; business-critical, must catch up after a stall.
#   - payment_reconciliation: 180s; the most critical, and a missed payment is
#     real money, so allow a longer recovery window.
#   - broadcasts: 30s only; a broadcast is a queue in PostgreSQL, so a late
#     start is recovered by the next tick regardless.
#
# coalesce: collapse a backlog of missed runs into ONE execution.
#   - True for all of them. Every job here is a *poller over durable database
#     state*, not a per-tick event consumer: running it once or five times
#     processes the same pending set. Coalescing therefore loses nothing and
#     prevents a pile-up after a stall.
#
# max_instances: prevent self-overlap.
#   - 1 everywhere. A second concurrent run of the same job adds no value
#     (the work is already idempotent and DB-guarded) and would only compete
#     for the connection pool. The Redis lock in @scheduled_job is the
#     cross-process guard; max_instances is the in-process one.
JOB_DEFAULTS: dict[str, dict[str, Any]] = {
    "payment_reconciliation": {
        "misfire_grace_time": 180,
        "coalesce": True,
        "max_instances": 1,
    },
    "process_orders": {"misfire_grace_time": 120, "coalesce": True, "max_instances": 1},
    "cleanup_expired": {"misfire_grace_time": 120, "coalesce": True, "max_instances": 1},
    "process_broadcasts": {"misfire_grace_time": 30, "coalesce": True, "max_instances": 1},
}


def _on_job_misfire(event: JobExecutionEvent) -> None:
    """Record misfires with severity scaled to how long we were late."""
    job_id = event.job_id
    delay = max(0.0, (event.timestamp - event.scheduled_run_time).total_seconds())

    health = job_health.get(job_id)
    criticality = health.criticality if health else "low"

    if delay < 10:
        log = logger.info
    elif criticality in ("critical", "important") or delay < 60:
        log = logger.warning
    else:
        log = logger.error

    log(
        "Scheduler job misfired: job=%s delay=%.1fs criticality=%s",
        job_id,
        delay,
        criticality,
    )
    if health:
        health.record_misfire(delay)


async def setup_scheduler() -> bool:
    """Start the scheduler, the loop monitor, and the singleton lock.

    Returns True if the scheduler is running. A False return means another
    process already owns the scheduler and this process should not run one.
    """
    global _scheduler, _singleton, _loop_monitor_stop

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running; refusing to start a second one")
        return False

    from app.workers.broadcast_worker import process_broadcasts_job
    from app.workers.cleanup_worker import cleanup_expired_job
    from app.workers.order_worker import process_paid_orders_job
    from app.workers.payment_worker import payment_reconciliation_job

    # Register health records before APScheduler starts so misfire events and
    # the admin health view always find them.
    for job_id in JOB_DEFAULTS:
        job_health.register(
            job_id,
            criticality="critical"
            if job_id in ("payment_reconciliation", "process_orders")
            else ("important" if job_id == "process_broadcasts" else "low"),
            slow_threshold=10.0
            if job_id in ("payment_reconciliation", "process_broadcasts")
            else 5.0,
        )

    # Guarantee a single scheduler across processes. A Redis outage must not
    # brick a single-instance deployment, so this proceeds with a loud warning.
    _singleton = SchedulerSingleton(ttl=60)
    if not await _singleton.acquire():
        logger.error(
            "Scheduler not started: another instance holds the scheduler lock. "
            "This process will serve Telegram updates only."
        )
        return False

    _scheduler = AsyncIOScheduler(
        timezone=settings.timezone,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )
    _scheduler.add_listener(_on_job_misfire, EVENT_JOB_MISSED)

    _scheduler.add_job(
        payment_reconciliation_job,
        "interval",
        seconds=settings.payment_reconciliation_interval_seconds,
        id="payment_reconciliation",
        **JOB_DEFAULTS["payment_reconciliation"],
    )
    _scheduler.add_job(
        cleanup_expired_job,
        "interval",
        seconds=60,
        id="cleanup_expired",
        **JOB_DEFAULTS["cleanup_expired"],
    )
    _scheduler.add_job(
        process_paid_orders_job,
        "interval",
        seconds=30,
        id="process_orders",
        **JOB_DEFAULTS["process_orders"],
    )
    _scheduler.add_job(
        process_broadcasts_job,
        "interval",
        seconds=10,
        id="process_broadcasts",
        **JOB_DEFAULTS["process_broadcasts"],
    )

    _scheduler.start(paused=True)
    # Run everything once at boot: this is the recovery path after a crash or
    # a restart that outlived the previous schedule.
    _scheduler.resume()
    for job_id in JOB_DEFAULTS:
        now_job = _scheduler.get_job(job_id)
        if now_job is not None:
            now_job.modify(next_run_time=datetime.now(_scheduler.timezone))

    _loop_monitor_stop = asyncio.Event()
    asyncio.create_task(
        monitor_event_loop_lag(
            interval=LOOP_MONITOR_INTERVAL,
            threshold=LOOP_MONITOR_THRESHOLD,
            stop_event=_loop_monitor_stop,
        )
    )

    logger.info(
        "Scheduler started with %s job(s)", len(JOB_DEFAULTS)
    )
    return True


async def shutdown_scheduler() -> None:
    """Stop jobs, cancel the loop monitor, and release the singleton lock."""
    global _scheduler, _singleton, _loop_monitor_stop

    if _loop_monitor_stop is not None:
        _loop_monitor_stop.set()
        _loop_monitor_stop = None

    if _scheduler is not None:
        # wait=True lets an in-flight job finish so we do not kill a payment
        # verification halfway through its transaction.
        _scheduler.shutdown(wait=True)
        _scheduler = None

    if _singleton is not None:
        await _singleton.release()
        _singleton = None

    logger.info("Scheduler stopped")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
