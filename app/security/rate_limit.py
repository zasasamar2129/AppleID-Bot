from __future__ import annotations

import time

from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, redis: Redis, enabled: bool = True):
        self.redis = redis
        self.enabled = enabled

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if allowed, False if rate limit exceeded."""
        if not self.enabled:
            return True
        current = int(time.time())
        window_start = current - window_seconds
        redis_key = f"rate_limit:{key}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zadd(redis_key, {str(current): current})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds)
            results = await pipe.execute()
        count = results[2]
        return count <= limit
