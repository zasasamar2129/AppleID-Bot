"""Redis distributed lock for scheduled jobs.

Two distinct guarantees are provided, because they solve different problems:

1. **Overlap guard** (``job_lock``) — prevents two executions of the same job
   running concurrently (e.g. a slow run overlapping the next interval tick).
   TTL is renewed while the job runs, so it cannot expire under a long job
   (the "lock TTL 30s, job runtime 2min" bug).

2. **Single-scheduler guard** (``SchedulerSingleton``) — ensures only one
   process in a deployment runs the scheduler. Held for the process lifetime
   with a heartbeat renewal.

Redis being unavailable fails *open* for overlap guards, because every worker
that uses one is also protected by a database-level conditional update — the
database is the real safety net, Redis is an optimisation.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.bot.bot import redis_client

logger = logging.getLogger(__name__)

# Compare-and-delete via Lua so we never delete another owner's lock after ours
# expired and someone else acquired it.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

# Extend TTL only if we still own the lock.
_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""


class _RedisLock:
    """A single Redis lock with owner token, TTL and automatic renewal.

    ``acquire`` is tri-state: ``True`` = acquired, ``False`` = someone else
    holds it, ``None`` = Redis was unreachable so we could not tell. Callers
    that must distinguish "another instance owns this" from "Redis is down"
    (the scheduler singleton) rely on the third value.
    """

    def __init__(self, redis: Redis, key: str, ttl: int) -> None:
        self.redis = redis
        self.key = key
        self.ttl = ttl
        self.token = secrets.token_hex(16)
        self._renew_task: asyncio.Task[None] | None = None

    async def acquire(self, blocking: bool = False, timeout: float = 0.0) -> bool | None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if await self.redis.set(self.key, self.token, nx=True, ex=self.ttl):
                    return True
            except RedisError as e:
                logger.error("Redis lock unavailable for %s: %s", self.key, type(e).__name__)
                return None
            if not blocking or time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.2)

    async def renew(self) -> bool:
        try:
            return bool(
                await self.redis.eval(_RENEW_LUA, 1, self.key, self.token, str(self.ttl))
            )
        except RedisError as e:
            logger.error("Lock renewal failed for %s: %s", self.key, type(e).__name__)
            return False

    async def release(self) -> None:
        self.stop_renewal()
        try:
            await self.redis.eval(_RELEASE_LUA, 1, self.key, self.token)
        except RedisError as e:
            logger.error("Failed to release lock %s: %s", self.key, type(e).__name__)

    def start_renewal(self) -> None:
        """Keep the TTL alive for the duration of a long-running critical section."""
        if self._renew_task is not None or self.ttl <= 0:
            return

        async def _renew() -> None:
            # Renew at 1/3 TTL so one missed beat is not fatal.
            interval = max(1.0, self.ttl / 3)
            while True:
                await asyncio.sleep(interval)
                if not await self.renew():
                    return

        self._renew_task = asyncio.create_task(_renew())

    def stop_renewal(self) -> None:
        if self._renew_task is not None:
            self._renew_task.cancel()
            self._renew_task = None


@asynccontextmanager
async def job_lock(
    job_id: str,
    ttl: int,
    redis: Redis | None = None,
    blocking: bool = False,
    timeout: float = 0.0,
) -> AsyncIterator[bool]:
    """Yield True if the lock was acquired, False if another run holds it.

    Fails open on Redis errors by yielding False: the caller skips this tick and
    relies on the job's database-level idempotency guard for correctness.
    """
    client = redis or redis_client
    lock = _RedisLock(client, f"joblock:{job_id}", ttl)
    # None (Redis down) is treated as "not acquired": skip this tick rather
    # than run unserialised, and let the next tick retry.
    if not await lock.acquire(blocking=blocking, timeout=timeout):
        yield False
        return
    lock.start_renewal()
    try:
        yield True
    finally:
        await lock.release()


class SchedulerSingleton:
    """Process-lifetime Redis lock guaranteeing one scheduler per deployment.

    If Redis is unreachable the scheduler still starts — a single-process
    deployment must not be bricked by a Redis outage — but it is logged loudly
    so the operator knows the guarantee is not in force.
    """

    def __init__(self, redis: Redis | None = None, ttl: int = 60) -> None:
        self.redis = redis or redis_client
        self.key = "scheduler:singleton"
        self.ttl = ttl
        self.token = secrets.token_hex(16)
        self._lock = _RedisLock(self.redis, self.key, ttl)
        self.acquired = False

    async def acquire(self) -> bool:
        """Return True if this process owns the scheduler lock.

        ``None`` from the lock means Redis was unreachable, not that another
        instance holds it. A single-process deployment must still start, so we
        proceed without the guarantee and log it loudly rather than silently
        running two schedulers.
        """
        result = await self._lock.acquire()
        if result is None:
            logger.error(
                "Redis unavailable; proceeding WITHOUT the single-scheduler "
                "guarantee. Do not run more than one instance until Redis is up."
            )
            self.acquired = True
            return True
        if not result:
            logger.error(
                "Another process already holds the scheduler lock (%s). "
                "Not starting the scheduler in this process.",
                self.key,
            )
            return False
        self.acquired = True
        self._lock.start_renewal()
        return True

    async def release(self) -> None:
        if self.acquired:
            await self._lock.release()
            self.acquired = False
