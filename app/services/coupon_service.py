from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.coupon import Coupon
from app.database.models.enums import CouponType
from app.database.repositories.coupon_repo import CouponRepository


class CouponService:
    def __init__(self, session: AsyncSession):
        self.coupon_repo = CouponRepository(session)

    async def validate_coupon(self, code: str, user_id: int, order_amount: Decimal, product_id: int | None = None) -> Coupon | None:
        coupon = await self.coupon_repo.get_by_code(code)
        if not coupon or not coupon.is_active:
            return None
        now = datetime.utcnow()
        if coupon.start_date and now < coupon.start_date:
            return None
        if coupon.end_date and now > coupon.end_date:
            return None
        if coupon.global_usage_limit and coupon.usage_count >= coupon.global_usage_limit:
            return None
        user_usage = await self.coupon_repo.get_user_usage_count(coupon.id, user_id)
        if user_usage >= coupon.per_user_limit:
            return None
        if coupon.min_order_amount and order_amount < coupon.min_order_amount:
            return None
        if product_id and coupon.product_restrictions:
            import json
            restricted = json.loads(coupon.product_restrictions)
            if product_id not in restricted:
                return None
        return coupon

    async def calculate_discount(self, coupon: Coupon, order_amount: Decimal) -> Decimal:
        if coupon.type == CouponType.PERCENTAGE:
            discount = order_amount * (coupon.value / Decimal("100"))
        else:
            discount = coupon.value
        if coupon.max_discount:
            discount = min(discount, coupon.max_discount)
        return min(discount, order_amount)  # don't allow negative

    async def apply_coupon(self, coupon: Coupon, user_id: int, order_id: int | None = None) -> None:
        await self.coupon_repo.increment_usage(coupon.id)
        await self.coupon_repo.add_usage(coupon.id, user_id, order_id)

    async def create_coupon(self, data: dict) -> Coupon:
        return await self.coupon_repo.create(data)

    async def get_all_coupons(self) -> list[Coupon]:
        return await self.coupon_repo.get_all()
