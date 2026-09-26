from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.broadcast import Broadcast, BroadcastReceipt


class BroadcastRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Broadcast:
        broadcast = Broadcast(**data)
        self.session.add(broadcast)
        await self.session.commit()
        await self.session.refresh(broadcast)
        return broadcast

    async def get_by_id(self, broadcast_id: int) -> Broadcast | None:
        return await self.session.get(Broadcast, broadcast_id)

    async def update(self, broadcast_id: int, data: dict) -> Broadcast | None:
        broadcast = await self.get_by_id(broadcast_id)
        if not broadcast:
            return None
        for key, value in data.items():
            setattr(broadcast, key, value)
        await self.session.commit()
        await self.session.refresh(broadcast)
        return broadcast

    async def add_receipt(self, broadcast_id: int, user_id: int, status: str) -> BroadcastReceipt:
        receipt = BroadcastReceipt(
            broadcast_id=broadcast_id,
            user_id=user_id,
            status=status,
        )
        self.session.add(receipt)
        await self.session.commit()
        await self.session.refresh(receipt)
        return receipt

    async def get_queued(self) -> list[Broadcast]:
        stmt = select(Broadcast).where(Broadcast.status == "queued").order_by(Broadcast.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_in_progress(self) -> list[Broadcast]:
        stmt = select(Broadcast).where(Broadcast.status == "in_progress")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
