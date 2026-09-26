from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.inventory import Inventory
from app.database.repositories.inventory_repo import InventoryRepository
from app.security.encryption import EncryptionService

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.inventory_repo = InventoryRepository(session)
        self.encryption = EncryptionService(settings.encryption_key)

    async def add_inventory(
        self,
        product_id: int,
        account_data: dict,
        fulfillment_data: dict | None = None,
        region: str | None = None,
        notes: str | None = None,
    ) -> Inventory:
        encrypted_account = self.encryption.encrypt(json.dumps(account_data))
        encrypted_fulfillment = None
        if fulfillment_data:
            encrypted_fulfillment = self.encryption.encrypt(json.dumps(fulfillment_data))
        return await self.inventory_repo.create(
            product_id=product_id,
            encrypted_account=encrypted_account,
            encrypted_fulfillment=encrypted_fulfillment,
            region=region,
            notes=notes,
        )

    async def get_by_id(self, inventory_id: int) -> Inventory | None:
        return await self.inventory_repo.get_by_id(inventory_id)

    async def reserve_inventory(self, inventory_id: int, reservation_seconds: int | None = None) -> Inventory | None:
        if reservation_seconds is None:
            reservation_seconds = settings.inventory_reservation_seconds
        return await self.inventory_repo.reserve(inventory_id, reservation_seconds)

    async def mark_sold(self, inventory_id: int) -> None:
        await self.inventory_repo.mark_sold(inventory_id)

    async def release_reservation(self, inventory_id: int) -> None:
        await self.inventory_repo.release_reservation(inventory_id)

    async def get_available_for_product(self, product_id: int) -> Inventory | None:
        return await self.inventory_repo.get_available_for_product(product_id)

    async def get_expired_reservations(self) -> list[Inventory]:
        return await self.inventory_repo.get_expired_reservations()

    async def decrypt_inventory(self, inventory: Inventory) -> dict | None:
        if not inventory or not inventory.encrypted_account_identifier:
            return None
        try:
            decrypted = self.encryption.decrypt(inventory.encrypted_account_identifier)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt inventory {inventory.id}: {e}")
            return None

    async def get_fulfillment_data(self, inventory: Inventory) -> dict | None:
        if not inventory or not inventory.encrypted_fulfillment_data:
            return None
        try:
            decrypted = self.encryption.decrypt(inventory.encrypted_fulfillment_data)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt fulfillment data {inventory.id}: {e}")
            return None
