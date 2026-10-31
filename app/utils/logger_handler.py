import json
import logging
from datetime import datetime
from typing import Any

from aiogram import Bot
from redis.asyncio import Redis

class RedisLoggingHandler(logging.Handler):
    def __init__(self, redis_client: Redis, bot: Bot, admin_ids: list[int], key: str = "bot:logs", max_logs: int = 50):
        super().__init__()
        self.redis = redis_client
        self.bot = bot
        self.admin_ids = admin_ids
        self.key = key
        self.max_logs = max_logs

    def emit(self, record: logging.LogRecord):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }

        try:
            # Safely get the running event loop.
            # During shutdown, this might raise a RuntimeError.
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._process_log(log_entry))
        except (RuntimeError, AttributeError):
            # No running loop, bot is shutting down.
            # Fallback to standard output so we don't crash.
            print(f"[{log_entry['level']}] {log_entry['message']}")

    async def _process_log(self, log_entry: dict[str, Any]):
        try:
            # Push to Redis list
            await self.redis.lpush(self.key, json.dumps(log_entry))
            await self.redis.ltrim(self.key, 0, self.max_logs - 1)

            # Alert on high severity
            if log_entry["level"] in ("ERROR", "CRITICAL"):
                for admin_id in self.admin_ids:
                    try:
                        await self.bot.send_message(
                            admin_id,
                            f"🚨 *Critical Log Alert*\n\n"
                            f"Level: {log_entry['level']}\n"
                            f"Time: {log_entry['timestamp']}\n"
                            f"Message: `{log_entry['message']}`",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
        except Exception as e:
            # Prevent logging errors from crashing the bot
            print(f"Logging handler error: {e}")
