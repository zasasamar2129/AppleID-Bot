from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import InventoryStatus, ProductType
from app.database.models.product import Product
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.product_repo import ProductRepository


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_repo = ProductRepository(session)
        self.inventory_repo = InventoryRepository(session)

    async def get_active_products(self, product_type: ProductType | None = None) -> list[Product]:
        return await self.product_repo.get_active(product_type)

    async def get_product(self, product_id: int) -> Product | None:
        return await self.product_repo.get_by_id(product_id)

    async def create_product(self, data: dict) -> Product:
        return await self.product_repo.create(data)

    async def update_product(self, product_id: int, data: dict) -> Product | None:
        return await self.product_repo.update(product_id, data)

    async def delete_product(self, product_id: int) -> tuple[bool, int]:
        """Delete a product (with its inventory) if it has no orders.

        Returns (deleted, order_count). If order_count > 0 the product is NOT
        deleted (callers should suggest deactivating instead).
        """
        order_count = await self.product_repo.count_orders(product_id)
        if order_count > 0:
            return False, order_count
        deleted = await self.product_repo.delete(product_id)
        return deleted, 0

    async def get_available_stock(self, product_id: int) -> int:
        # count available inventory for product
        # implement using inventory repo count by status and product
        from sqlalchemy import func, select

        from app.database.models.inventory import Inventory
        stmt = select(func.count()).select_from(Inventory).where(
            Inventory.product_id == product_id,
            Inventory.status == InventoryStatus.AVAILABLE
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
