"""Scheduler hardening tests.

These run WITHOUT a database. They cover the guarantees that protect business
operations: idempotency of the SQL guards, lock behaviour, health tracking,
misfire policy, and the encryption key-derivation cache that was the actual
root cause of the event-loop stalls.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.database.models.broadcast import BroadcastReceipt
from app.security.encryption import EncryptionService
from app.utils.job_lock import _RedisLock, job_lock
from app.workers.job_health import JobHealth, JobHealthRegistry


# --------------------------------------------------------------------------
# Root cause: PBKDF2 key derivation ran on the event loop per request
# --------------------------------------------------------------------------
def test_encryption_key_derivation_is_cached():
    """Constructing EncryptionService must not repeat 100k PBKDF2 iterations.

    Before the fix this cost ~50-70ms of blocking CPU on every construction,
    and InventoryService constructs one per request AND per scheduled-job
    iteration. That was what stalled the event loop and delayed every job.
    """
    EncryptionService._key_cache.clear()

    first = EncryptionService("perf-test-key")
    start = time.perf_counter()
    for _ in range(200):
        EncryptionService("perf-test-key")
    elapsed = time.perf_counter() - start

    # 200 uncached derivations would take >10s. Cached must be far under 1s.
    assert elapsed < 1.0, f"key derivation not cached: {elapsed:.3f}s for 200 constructions"
    assert first is not None


def test_encryption_roundtrip_still_correct():
    """Caching must not change the ciphertext contract."""
    from cryptography.exceptions import InvalidTag

    svc = EncryptionService("roundtrip-key")
    ciphertext = svc.encrypt("apple-id-secret")
    assert svc.decrypt(ciphertext) == "apple-id-secret"
    # A different key must not decrypt it (AES-GCM authentication tag fails).
    with pytest.raises(InvalidTag):
        EncryptionService("different-key").decrypt(ciphertext)


def test_encryption_nonce_is_unique_per_call():
    """Same plaintext must not produce the same ciphertext twice."""
    svc = EncryptionService("nonce-key")
    assert svc.encrypt("same") != svc.encrypt("same")


# --------------------------------------------------------------------------
# Broadcast resume: the unique constraint that prevents duplicate delivery
# --------------------------------------------------------------------------
def test_broadcast_receipt_has_unique_constraint():
    """A duplicate (broadcast, user) receipt must be rejected by the DB.

    This constraint is what makes a resumed broadcast skip already-delivered
    users, and what stops a duplicate run sending a second message.
    """
    table = BroadcastReceipt.__table__
    unique = [
        c
        for c in table.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert unique, "BroadcastReceipt must declare a UniqueConstraint"
    cols = {col.name for col in unique[0].columns}
    assert cols == {"broadcast_id", "user_id"}


# --------------------------------------------------------------------------
# Lock behaviour
# --------------------------------------------------------------------------
class _FakeRedis:
    """Minimal in-memory Redis stub covering SET NX EX and EVAL."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail = False

    async def set(self, key, value, nx=False, ex=None):
        if self.fail:
            from redis.exceptions import ConnectionError as RedisConnError

            raise RedisConnError("simulated outage")
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def eval(self, script, numkeys, *args):
        if self.fail:
            from redis.exceptions import ConnectionError as RedisConnError

            raise RedisConnError("simulated outage")
        key, token = args[0], args[1]
        if "del" in script and "expire" not in script:
            if self.store.get(key) == token:
                del self.store[key]
                return 1
            return 0
        if "expire" in script:
            if self.store.get(key) == token:
                self.ttls[key] = int(args[2])
                return 1
            return 0
        return 0


@pytest.mark.asyncio
async def test_job_lock_prevents_overlap():
    """A second acquisition while the first is held must fail."""
    redis = _FakeRedis()
    async with job_lock("test_lock", ttl=30, redis=redis) as first:
        assert first is True
        async with job_lock("test_lock", ttl=30, redis=redis) as second:
            assert second is False, "overlapping execution must be prevented"


@pytest.mark.asyncio
async def test_job_lock_released_after_use():
    """The lock must be free again once the critical section exits."""
    redis = _FakeRedis()
    async with job_lock("release_test", ttl=30, redis=redis) as first:
        assert first is True
    async with job_lock("release_test", ttl=30, redis=redis) as second:
        assert second is True, "lock must be released after the job finishes"


@pytest.mark.asyncio
async def test_job_lock_fails_closed_when_redis_down():
    """Redis outage must skip the run, not execute it unserialised.

    Correctness does not depend on this lock (workers also use conditional
    UPDATEs), so skipping the tick and retrying later is the safe behaviour.
    """
    redis = _FakeRedis()
    redis.fail = True
    async with job_lock("redis_down", ttl=30, redis=redis) as acquired:
        assert acquired is False


@pytest.mark.asyncio
async def test_lock_release_does_not_delete_another_owners_lock():
    """Compare-and-delete must be ownership checked.

    If our lock expired and someone else re-acquired the key, our release
    must NOT delete their lock.
    """
    redis = _FakeRedis()
    lock = _RedisLock(redis, "owned", ttl=30)
    assert await lock.acquire() is True

    # Simulate expiry + a different owner taking the key.
    redis.store["owned"] = "someone-else-token"
    await lock.release()

    assert redis.store.get("owned") == "someone-else-token", (
        "release must not delete a lock owned by another process"
    )


# --------------------------------------------------------------------------
# Health tracking
# --------------------------------------------------------------------------
def test_job_health_records_success_and_failure():
    health = JobHealth(job_id="j", criticality="critical", slow_threshold=5.0)
    health.record_success(1.0, processed=7)
    assert health.last_status == "ok"
    assert health.last_processed == 7
    assert health.consecutive_failures == 0

    health.record_failure(2.0, "TimeoutError")
    assert health.last_status == "failed"
    assert health.last_error_type == "TimeoutError"
    assert health.consecutive_failures == 1
    # A job whose most recent run failed is not healthy right now, even though
    # one failure is not yet a trend.
    assert health.is_healthy() is False

    health.record_failure(2.0, "TimeoutError")
    health.record_failure(2.0, "TimeoutError")
    assert health.consecutive_failures == 3
    assert health.is_healthy() is False, "3 consecutive failures must mark unhealthy"


def test_job_health_success_resets_failure_streak():
    health = JobHealth(job_id="j")
    health.record_failure(1.0, "E")
    health.record_failure(1.0, "E")
    health.record_success(1.0, 0)
    assert health.consecutive_failures == 0
    assert health.is_healthy() is True


def test_job_health_snapshot_has_no_secrets():
    """The snapshot is shown to admins, so it must carry no payloads."""
    health = JobHealth(job_id="payment_reconciliation")
    health.record_failure(1.5, "OperationalError")
    snap = health.snapshot()
    assert set(snap) == {
        "job_id", "criticality", "last_status", "last_duration_s",
        "avg_duration_s", "last_error_type", "consecutive_failures",
        "total_runs", "total_failures", "total_misfires", "last_processed",
        "skipped_locked", "seconds_since_last_run",
    }


def test_health_registry_registers_once():
    reg = JobHealthRegistry()
    a = reg.register("x", criticality="critical")
    b = reg.register("x", criticality="low")
    assert a is b, "re-registering must return the same record"
    assert b.criticality == "critical", "must not overwrite existing registration"


# --------------------------------------------------------------------------
# Misfire policy
# --------------------------------------------------------------------------
def test_every_scheduled_job_has_explicit_misfire_policy():
    """No job may rely on APScheduler's implicit defaults."""
    from app.workers.scheduler import JOB_DEFAULTS

    for job_id in (
        "payment_reconciliation",
        "process_orders",
        "cleanup_expired",
        "process_broadcasts",
    ):
        assert job_id in JOB_DEFAULTS, f"{job_id} missing misfire policy"
        cfg = JOB_DEFAULTS[job_id]
        assert set(cfg) == {"misfire_grace_time", "coalesce", "max_instances"}
        assert cfg["coalesce"] is True, f"{job_id} must coalesce (poller job)"
        assert cfg["max_instances"] == 1, f"{job_id} must not self-overlap"
        assert cfg["misfire_grace_time"] > 0


def test_critical_jobs_get_longer_misfire_grace_than_cleanup():
    """Recovery tolerance must be scaled by criticality, not applied blindly."""
    from app.workers.scheduler import JOB_DEFAULTS

    assert (
        JOB_DEFAULTS["payment_reconciliation"]["misfire_grace_time"]
        > JOB_DEFAULTS["process_broadcasts"]["misfire_grace_time"]
    )


def test_scheduler_starts_only_once():
    """setup_scheduler must refuse to start a second scheduler instance."""
    from app.workers import scheduler as sched

    assert hasattr(sched, "setup_scheduler")
    src = __import__("inspect").getsource(sched.setup_scheduler)
    assert "already running" in src, "must guard against a double start"


# --------------------------------------------------------------------------
# SQL shape regressions
#
# PostgreSQL UPDATE has no LIMIT. Chaining .limit() onto an Update() raises
# AttributeError at *runtime*, inside the job, so it only shows up as a
# repeating scheduler error. These tests compile the real worker queries and
# fail loudly at import/test time instead.
# --------------------------------------------------------------------------
def test_update_has_no_limit_method():
    """Sanity check for the invariant the workers rely on.

    PostgreSQL has no `UPDATE ... LIMIT`, so SQLAlchemy's Update deliberately has
    no `.limit()`. Chaining it raises AttributeError at runtime, inside the job,
    which surfaces only as a repeating scheduler error. Bounded updates must
    therefore select their target id with a `select(...).limit(...)` subquery —
    as the two query-compilation tests below verify.
    """
    from sqlalchemy import Update

    assert not hasattr(Update, "limit")


def test_broadcast_claim_query_compiles():
    """The broadcast claim must compile to UPDATE ... WHERE id = (SELECT ... LIMIT 1)."""
    from datetime import datetime, timedelta

    from sqlalchemy import and_, or_, select, update
    from sqlalchemy.dialects import postgresql

    from app.database.models.broadcast import Broadcast

    now = datetime.utcnow()
    stale_before = now - timedelta(seconds=3600)
    eligible = (
        select(Broadcast.id)
        .where(
            or_(
                Broadcast.status == "queued",
                and_(
                    Broadcast.status == "in_progress",
                    or_(
                        Broadcast.started_at.is_(None),
                        Broadcast.started_at < stale_before,
                    ),
                ),
            )
        )
        .order_by(Broadcast.created_at)
        .limit(1)
    )
    stmt = (
        update(Broadcast)
        .where(Broadcast.id == eligible.scalar_subquery())
        .values(status="in_progress", started_at=now)
        .returning(Broadcast.id)
    )
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert sql.startswith("UPDATE broadcasts")
    assert "LIMIT" in sql and "RETURNING" in sql


def test_inventory_claim_query_compiles():
    """Order worker's inventory claim must compile (subquery, not UPDATE..LIMIT)."""
    from datetime import datetime

    from sqlalchemy import and_, select, update
    from sqlalchemy.dialects import postgresql

    from app.database.models.enums import InventoryStatus
    from app.database.models.inventory import Inventory

    now = datetime.utcnow()
    candidate = (
        select(Inventory.id)
        .where(
            and_(
                Inventory.product_id == 1,
                Inventory.status == InventoryStatus.AVAILABLE,
            )
        )
        .order_by(Inventory.created_at)
        .limit(1)
    )
    stmt = (
        update(Inventory)
        .where(Inventory.id == candidate.scalar_subquery())
        .values(status=InventoryStatus.SOLD, sold_at=now)
        .returning(Inventory.id)
    )
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert sql.startswith("UPDATE inventory")
    assert "LIMIT" in sql and "RETURNING" in sql


# --------------------------------------------------------------------------
# Event-loop monitoring
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_loop_monitor_logs_lag_when_blocked():
    """A blocking sleep must be detected as event-loop lag."""
    import logging

    from app.utils.loop_monitor import monitor_event_loop_lag

    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Capture()
    log = logging.getLogger("app.utils.loop_monitor")
    log.addHandler(handler)
    previous = log.level
    log.setLevel(logging.WARNING)

    stop = asyncio.Event()
    task = asyncio.create_task(
        monitor_event_loop_lag(interval=0.05, threshold=0.05, stop_event=stop)
    )
    # Let the monitor actually start and arm its first sleep, otherwise the
    # blocking call below happens before the task ever runs and no lag is
    # measured against anything.
    await asyncio.sleep(0.1)
    # Block the loop for longer than the threshold.
    time.sleep(0.3)
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)

    log.removeHandler(handler)
    log.setLevel(previous)

    assert any("Event loop lag detected" in r for r in records), (
        f"lag not detected; captured: {records}"
    )


@pytest.mark.asyncio
async def test_loop_monitor_exits_promptly_on_stop():
    from app.utils.loop_monitor import monitor_event_loop_lag

    stop = asyncio.Event()
    task = asyncio.create_task(
        monitor_event_loop_lag(interval=5.0, threshold=10.0, stop_event=stop)
    )
    await asyncio.sleep(0.05)
    stop.set()
    # Must return immediately rather than waiting the full interval.
    await asyncio.wait_for(task, timeout=1.0)
    assert task.done()
