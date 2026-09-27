import pytest
from decimal import Decimal
from app.database.models.enums import ProductType, DeliveryType, OrderStatus
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.product_repo import ProductRepository
from app.services.order_service import OrderService

@pytest.mark.asyncio
async def test_create_order(db_session):
    user_repo = UserRepository(db_session)
    user = await user_repo.create(telegram_id=123456, first_name="Test")
    product_repo = ProductRepository(db_session)
    product = await product_repo.create({
        "name": "Test Product",
        "type": ProductType.PERSONAL,
        "price": Decimal("100"),
        "currency": "IRR",
        "delivery_type": DeliveryType.MANUAL,
    })
    order_service = OrderService(db_session)
    order = await order_service.create_order(
        user_id=user.id,
        product_id=product.id,
        order_type=ProductType.PERSONAL,
        price=Decimal("100"),
        final_price=Decimal("100"),
    )
    assert order.id is not None
    assert order.status == OrderStatus.PENDING_PAYMENT