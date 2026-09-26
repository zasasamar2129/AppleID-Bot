from __future__ import annotations

import asyncio
import logging

from app.bot.bot import bot
from app.config import settings
from app.database.repositories.broadcast_repo import BroadcastRepository
from app.database.repositories.user_repo import UserRepository
from app.database.session import async_session

logger = logging.getLogger(__name__)


async def process_broadcasts_job():
    async with async_session() as session:
        broadcast_repo = BroadcastRepository(session)
        queued = await broadcast_repo.get_queued()
        for b in queued:
            await broadcast_repo.update(b.id, {"status": "in_progress"})
            user_repo = UserRepository(session)
            users = await user_repo.get_all(limit=10000)  # In reality, filter by audience
            for user in users:
                try:
                    if b.content_type == "text":
                        await bot.send_message(chat_id=user.telegram_id, text=b.content)
                    # handle other types later
                    await broadcast_repo.add_receipt(b.id, user.id, "sent")
                    await broadcast_repo.update_stats(b.id, sent=1)
                except Exception:
                    await broadcast_repo.add_receipt(b.id, user.id, "failed")
                    await broadcast_repo.update_stats(b.id, failed=1)
                await asyncio.sleep(settings.broadcast_delay_seconds)
            await broadcast_repo.update(b.id, {"status": "completed"})
        await session.commit()
