from __future__ import annotations

import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter backed by Redis.

    Fails OPEN: if Redis is unreachable the limit is not enforced and the caller
    is allowed through. Rate limiting is a courtesy, not a security control, and
    an unreachable Redis must never take the whole bot down with it — that bug
    silently killed every update before it reached a handler.
    """

    def __init__(self, redis: Redis, enabled: bool = True):
        self.redis = redis
        self.enabled = enabled

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if allowed, False if rate limit exceeded.

        Returns True (allow) whenever the underlying store is unavailable.
        """
        if not self.enabled:
            return True
        current = int(time.time())
        window_start = current - window_seconds
        redis_key = f"rate_limit:{key}"
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, 0, window_start)
                pipe.zadd(redis_key, {str(current): current})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, window_seconds)
                results = await pipe.execute()
        except RedisError as e:
            # Fail open — see the class docstring. Logged once per failure so a
            # Redis outage is visible without spamming every update.
            logger.warning(
                "Rate limiter unavailable (%s); allowing request for %s",
                type(e).__name__,
                redis_key,
            )
            return True
        except Exception:
            logger.exception("Unexpected rate limiter failure for %s", redis_key)
            return True
        count = results[2]
        return count <= limit
