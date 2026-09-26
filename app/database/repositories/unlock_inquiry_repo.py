from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.unlock_inquiry import UnlockInquiry
from app.database.models.enums import UnlockInquiryStatus


class UnlockInquiryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        model: str,
        apple_id_email: str,
        customer_phone: str,
        has_credentials: str,
    ) -> UnlockInquiry:
        item = UnlockInquiry(
            user_id=user_id,
            model=model,
            apple_id_email=apple_id_email,
            customer_phone=customer_phone,
            has_credentials=has_credentials,
            status=UnlockInquiryStatus.PENDING,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_by_id(self, inquiry_id: int) -> UnlockInquiry | None:
        return await self.session.get(UnlockInquiry, inquiry_id)

    async def get_by_user(self, user_id: int, limit: int = 20) -> list[UnlockInquiry]:
        stmt = (
            select(UnlockInquiry)
            .where(UnlockInquiry.user_id == user_id)
            .order_by(UnlockInquiry.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: UnlockInquiryStatus, limit: int = 50) -> list[UnlockInquiry]:
        stmt = (
            select(UnlockInquiry)
            .where(UnlockInquiry.status == status)
            .order_by(UnlockInquiry.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, inquiry_id: int, status: UnlockInquiryStatus) -> UnlockInquiry | None:
        item = await self.get_by_id(inquiry_id)
        if item:
            item.status = status
            item.updated_at = datetime.utcnow()
            if status == UnlockInquiryStatus.COMPLETED:
                item.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(item)
        return item

    async def update(self, inquiry_id: int, data: dict) -> UnlockInquiry | None:
        item = await self.get_by_id(inquiry_id)
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[UnlockInquiry]:
        stmt = (
            select(UnlockInquiry)
            .order_by(UnlockInquiry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())