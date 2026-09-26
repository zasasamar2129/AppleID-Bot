from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.price_inquiry import PriceInquiry


class PriceInquiryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> PriceInquiry:
        item = PriceInquiry(**data)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_by_id(self, item_id: int) -> PriceInquiry | None:
        return await self.session.get(PriceInquiry, item_id)

    async def get_active(self) -> list[PriceInquiry]:
        stmt = select(PriceInquiry).where(PriceInquiry.is_active == True).order_by(PriceInquiry.sort_order)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, include_inactive: bool = True) -> list[PriceInquiry]:
        stmt = select(PriceInquiry)
        if not include_inactive:
            stmt = stmt.where(PriceInquiry.is_active == True)
        stmt = stmt.order_by(PriceInquiry.sort_order)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, item_id: int, data: dict) -> PriceInquiry | None:
        item = await self.get_by_id(item_id)
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item_id: int) -> None:
        item = await self.get_by_id(item_id)
        if item:
            await self.session.delete(item)
            await self.session.commit()
