from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.broadcast import Broadcast
from app.database.repositories.broadcast_repo import BroadcastRepository
from app.database.repositories.user_repo import UserRepository


class BroadcastService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.broadcast_repo = BroadcastRepository(session)
        self.user_repo = UserRepository(session)

    async def create_broadcast(self, admin_id: int, content_type: str, content: str, caption: str | None = None, inline_buttons_json: str | None = None, audience_filter: dict | None = None) -> Broadcast:
        data = {
            "admin_id": admin_id,
            "content_type": content_type,
            "content": content,
            "caption": caption,
            "inline_buttons_json": inline_buttons_json,
            "audience_filter": json.dumps(audience_filter) if audience_filter else "{}",
            "target_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "status": "queued",
        }
        return await self.broadcast_repo.create(data)

    async def get_audience_count(self, audience_filter: dict) -> int:
        # Implement filtering logic
        # For now, simple count of all users
        return await self.user_repo.count()

    async def queue_broadcast(self, broadcast_id: int, target_count: int) -> None:
        await self.broadcast_repo.update(broadcast_id, {"target_count": target_count, "status": "queued"})

    async def get_pending_broadcasts(self) -> list[Broadcast]:
        return await self.broadcast_repo.get_queued()

    async def mark_started(self, broadcast_id: int) -> None:
        await self.broadcast_repo.update(broadcast_id, {"status": "in_progress"})

    async def update_stats(self, broadcast_id: int, sent: int = 0, failed: int = 0, blocked: int = 0) -> None:
        b = await self.broadcast_repo.get_by_id(broadcast_id)
        if b:
            await self.broadcast_repo.update(broadcast_id, {
                "sent_count": b.sent_count + sent,
                "failed_count": b.failed_count + failed,
                "blocked_count": b.blocked_count + blocked,
            })

    async def mark_completed(self, broadcast_id: int) -> None:
        from datetime import datetime
        await self.broadcast_repo.update(broadcast_id, {"status": "completed", "completed_at": datetime.utcnow()})
