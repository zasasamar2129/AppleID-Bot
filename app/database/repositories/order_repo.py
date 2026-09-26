from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.enums import OrderStatus, PaymentMethod
from app.database.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Order:
        order = Order(**data)
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def get_by_id(self, order_id: int) -> Order | None:
        stmt = select(Order).options(selectinload(Order.product), selectinload(Order.user)).where(Order.id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Order]:
        stmt = select(Order).options(selectinload(Order.product)).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: OrderStatus, limit: int = 100, offset: int = 0) -> list[Order]:
        stmt = select(Order).options(selectinload(Order.product), selectinload(Order.user)).where(Order.status == status).order_by(Order.created_at).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, order_id: int, new_status: OrderStatus, extra: dict | None = None) -> Order | None:
        order = await self.get_by_id(order_id)
        if not order:
            return None
        order.status = new_status
        if extra:
            for key, value in extra.items():
                setattr(order, key, value)
        order.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def set_payment_method(self, order_id: int, method: PaymentMethod) -> None:
        order = await self.get_by_id(order_id)
        if order:
            order.payment_method = method
            await self.session.commit()

    async def add_admin_note(self, order_id: int, note: str) -> None:
        order = await self.get_by_id(order_id)
        if order:
            order.admin_notes = (order.admin_notes or "") + f"\n{note}"
            await self.session.commit()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(Order)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_status(self, status: OrderStatus | None = None) -> int:
        stmt = select(func.count()).select_from(Order)
        if status:
            stmt = stmt.where(Order.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Order]:
        stmt = select(Order).options(selectinload(Order.product), selectinload(Order.user)).order_by(Order.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
