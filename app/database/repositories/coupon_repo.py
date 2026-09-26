from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.coupon import Coupon, CouponUsage


class CouponRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Coupon:
        coupon = Coupon(**data)
        self.session.add(coupon)
        await self.session.commit()
        await self.session.refresh(coupon)
        return coupon

    async def get_by_code(self, code: str) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, coupon_id: int) -> Coupon | None:
        return await self.session.get(Coupon, coupon_id)

    async def update(self, coupon_id: int, data: dict) -> Coupon | None:
        coupon = await self.get_by_id(coupon_id)
        if not coupon:
            return None
        for key, value in data.items():
            setattr(coupon, key, value)
        coupon.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(coupon)
        return coupon

    async def increment_usage(self, coupon_id: int) -> None:
        coupon = await self.get_by_id(coupon_id)
        if coupon:
            coupon.usage_count += 1
            await self.session.commit()

    async def add_usage(self, coupon_id: int, user_id: int, order_id: int | None = None) -> CouponUsage:
        usage = CouponUsage(coupon_id=coupon_id, user_id=user_id, order_id=order_id)
        self.session.add(usage)
        await self.session.commit()
        await self.session.refresh(usage)
        return usage

    async def get_user_usage_count(self, coupon_id: int, user_id: int) -> int:
        stmt = select(CouponUsage).where(CouponUsage.coupon_id == coupon_id, CouponUsage.user_id == user_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def get_all(self) -> list[Coupon]:
        stmt = select(Coupon).order_by(Coupon.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, coupon_id: int) -> None:
        coupon = await self.get_by_id(coupon_id)
        if coupon:
            await self.session.delete(coupon)
            await self.session.commit()
