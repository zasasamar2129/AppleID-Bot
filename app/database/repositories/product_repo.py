from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import ProductType
from app.database.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Product:
        product = Product(**data)
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def get_by_id(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_active(self, product_type: ProductType | None = None) -> list[Product]:
        stmt = select(Product).where(Product.is_active == True)
        if product_type:
            stmt = stmt.where(Product.type == product_type)
        stmt = stmt.order_by(Product.sort_order)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, product_id: int, data: dict) -> Product | None:
        product = await self.get_by_id(product_id)
        if not product:
            return None
        for key, value in data.items():
            setattr(product, key, value)
        product.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def set_active(self, product_id: int, active: bool) -> None:
        product = await self.get_by_id(product_id)
        if product:
            product.is_active = active
            product.updated_at = datetime.utcnow()
            await self.session.commit()

    async def get_all(self, include_inactive: bool = False) -> list[Product]:
        stmt = select(Product)
        if not include_inactive:
            stmt = stmt.where(Product.is_active == True)
        stmt = stmt.order_by(Product.sort_order)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_orders(self, product_id: int) -> int:
        from sqlalchemy import func
        from app.database.models.order import Order
        stmt = select(func.count()).select_from(Order).where(Order.product_id == product_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete(self, product_id: int) -> bool:
        """Hard-delete a product. Returns True if deleted.

        Only safe when no orders reference it. Callers must check
        count_orders() first; otherwise use set_active(product_id, False).
        """
        product = await self.get_by_id(product_id)
        if not product:
            return False
        from app.database.models.inventory import Inventory
        from sqlalchemy import select as sa_select
        inv_stmt = sa_select(Inventory).where(Inventory.product_id == product_id)
        inventories = (await self.session.execute(inv_stmt)).scalars().all()
        for inv in inventories:
            await self.session.delete(inv)
        await self.session.delete(product)
        await self.session.commit()
        return True
