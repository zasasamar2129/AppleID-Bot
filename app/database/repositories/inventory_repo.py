from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.enums import InventoryStatus
from app.database.models.inventory import Inventory


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        product_id: int,
        encrypted_account: str,
        encrypted_fulfillment: str | None = None,
        region: str | None = None,
        notes: str | None = None,
    ) -> Inventory:
        inv = Inventory(
            product_id=product_id,
            region=region,
            status=InventoryStatus.AVAILABLE,
            encrypted_account_identifier=encrypted_account,
            encrypted_fulfillment_data=encrypted_fulfillment,
            internal_notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(inv)
        await self.session.commit()
        await self.session.refresh(inv)
        return inv

    async def get_by_id(self, inventory_id: int) -> Inventory | None:
        return await self.session.get(Inventory, inventory_id)

    async def get_available_for_product(self, product_id: int) -> Inventory | None:
        stmt = select(Inventory).where(
            Inventory.product_id == product_id,
            Inventory.status == InventoryStatus.AVAILABLE
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reserve(self, inventory_id: int, reservation_seconds: int) -> Inventory | None:
        inv = await self.get_by_id(inventory_id)
        if not inv or inv.status != InventoryStatus.AVAILABLE:
            return None
        now = datetime.utcnow()
        inv.status = InventoryStatus.RESERVED
        inv.reserved_at = now
        inv.reservation_expires_at = now + timedelta(seconds=reservation_seconds)
        inv.updated_at = now
        await self.session.commit()
        await self.session.refresh(inv)
        return inv

    async def mark_sold(self, inventory_id: int) -> None:
        inv = await self.get_by_id(inventory_id)
        if inv:
            inv.status = InventoryStatus.SOLD
            inv.sold_at = datetime.utcnow()
            inv.updated_at = datetime.utcnow()
            inv.reservation_expires_at = None
            await self.session.commit()

    async def release_reservation(self, inventory_id: int) -> None:
        inv = await self.get_by_id(inventory_id)
        if inv and inv.status == InventoryStatus.RESERVED:
            inv.status = InventoryStatus.AVAILABLE
            inv.reserved_at = None
            inv.reservation_expires_at = None
            inv.updated_at = datetime.utcnow()
            await self.session.commit()

    async def set_disabled(self, inventory_id: int, disabled: bool) -> None:
        inv = await self.get_by_id(inventory_id)
        if inv:
            inv.status = InventoryStatus.DISABLED if disabled else InventoryStatus.AVAILABLE
            inv.updated_at = datetime.utcnow()
            await self.session.commit()

    async def count_by_status(self, status: InventoryStatus) -> int:
        stmt = select(func.count()).select_from(Inventory).where(Inventory.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_expired_reservations(self) -> list[Inventory]:
        now = datetime.utcnow()
        stmt = select(Inventory).where(
            Inventory.status == InventoryStatus.RESERVED,
            Inventory.reservation_expires_at < now
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(
        self, status: InventoryStatus | None = None, limit: int = 100, offset: int = 0
    ) -> list[Inventory]:
        stmt = select(Inventory).options(selectinload(Inventory.product))
        if status:
            stmt = stmt.where(Inventory.status == status)
        stmt = stmt.order_by(Inventory.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
