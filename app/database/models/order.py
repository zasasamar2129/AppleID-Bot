from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.enums import OrderStatus, OrderType, PaymentMethod


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=True)
    inventory_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory.id"), nullable=True)
    order_type: Mapped[OrderType] = mapped_column(SAEnum(OrderType, name='ordertype'))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    final_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="IRR")
    payment_method: Mapped[PaymentMethod | None] = mapped_column(SAEnum(PaymentMethod), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.PENDING_PAYMENT, index=True)
    customer_information: Mapped[dict | None] = mapped_column(Text, nullable=True)  # JSON string
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    inventory = relationship("Inventory", back_populates="order")
    payment = relationship("Payment", uselist=False, back_populates="order")
