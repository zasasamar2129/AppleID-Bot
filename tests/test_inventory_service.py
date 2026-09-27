import pytest
from decimal import Decimal
from app.database.models.enums import ProductType, DeliveryType
from app.database.repositories.product_repo import ProductRepository
from app.services.inventory_service import InventoryService

@pytest.mark.asyncio
async def test_reserve_inventory(db_session):
    # Create product
    product_repo = ProductRepository(db_session)
    product = await product_repo.create({
        "name": "Test Product",
        "type": ProductType.READY_MADE,
        "price": Decimal("100"),
        "currency": "IRR",
        "delivery_type": DeliveryType.AUTOMATIC,
    })
    inventory_service = InventoryService(db_session)
    inv = await inventory_service.add_inventory(product.id, {"email": "test@test.com", "password": "secret"})
    # Reserve
    reserved = await inventory_service.reserve_inventory(inv.id, reservation_seconds=600)
    assert reserved is not None
    assert reserved.status.value == "reserved"
    # Try to reserve again should fail
    reserved2 = await inventory_service.reserve_inventory(inv.id, reservation_seconds=600)
    assert reserved2 is None
    # Release
    await inventory_service.release_reservation(inv.id)
    # Fetch again
    from app.database.repositories.inventory_repo import InventoryRepository
    repo = InventoryRepository(db_session)
    fetched = await repo.get_by_id(inv.id)
    assert fetched.status.value == "available"