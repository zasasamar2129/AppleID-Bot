from __future__ import annotations

import asyncio
import logging
import sys

from app.bot.bot import bot, dp, redis_client
from app.bot.dispatcher import register_all_routers, setup_middlewares
from app.config import settings
from app.database.models.enums import AdminRole
from app.database.repositories.admin_repo import AdminRepository
from app.database.session import async_session, engine
from app.workers.scheduler import setup_scheduler, shutdown_scheduler


class ColoredFormatter(logging.Formatter):
    """Logging formatter with ANSI colors."""

    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[1;31m", # Bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
root_logger.addHandler(handler)

# Suppress noisy loggers
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def bootstrap_admins():
    async with async_session() as session:
        repo = AdminRepository(session)
        for telegram_id in settings.admin_ids_list:
            existing = await repo.get_by_telegram_id(telegram_id)
            if not existing:
                await repo.create(
                    telegram_id=telegram_id,
                    first_name="Admin",
                    role=AdminRole.SUPER_ADMIN,
                )
                logger.info(f"Bootstrapped admin {telegram_id}")
        await session.commit()


async def on_startup():
    await bootstrap_admins()
    setup_middlewares(dp)
    register_all_routers(dp)

    # Validate the mandatory channel is reachable (logs a clear admin warning;
    # never crashes startup, never exposes technical errors to users).
    from app.services.channel_membership_service import ChannelMembershipService
    await ChannelMembershipService(bot).check_channel_access()

    setup_scheduler()
    logger.info("Bot started")


async def on_shutdown():
    shutdown_scheduler()
    await bot.session.close()
    await redis_client.aclose()
    await engine.dispose()
    logger.info("Bot stopped")


async def main():
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot interrupted")
