from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import UnlockPaymentStatus, UnlockRequestStatus
from app.database.models.unlock_request import UnlockRequest


class UnlockRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> UnlockRequest:
        req = UnlockRequest(**data)
        self.session.add(req)
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def get_by_id(self, request_id: int) -> UnlockRequest | None:
        return await self.session.get(UnlockRequest, request_id)

    async def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[UnlockRequest]:
        stmt = (
            select(UnlockRequest)
            .where(UnlockRequest.user_id == user_id)
            .order_by(UnlockRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: UnlockRequestStatus, limit: int = 50, offset: int = 0) -> list[UnlockRequest]:
        stmt = (
            select(UnlockRequest)
            .where(UnlockRequest.status == status)
            .order_by(UnlockRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[UnlockRequest]:
        stmt = (
            select(UnlockRequest)
            .order_by(UnlockRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, request_id: int, data: dict) -> UnlockRequest | None:
        req = await self.get_by_id(request_id)
        if not req:
            return None
        for key, value in data.items():
            setattr(req, key, value)
        req.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def update_status(self, request_id: int, status: UnlockRequestStatus) -> UnlockRequest | None:
        req = await self.get_by_id(request_id)
        if not req:
            return None
        req.status = status
        req.updated_at = datetime.utcnow()
        if status == UnlockRequestStatus.COMPLETED:
            req.completed_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def update_payment_status(self, request_id: int, payment_status: UnlockPaymentStatus) -> UnlockRequest | None:
        req = await self.get_by_id(request_id)
        if not req:
            return None
        req.payment_status = payment_status
        req.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(UnlockRequest)
        result = await self.session.execute(stmt)
        return result.scalar_one()