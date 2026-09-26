from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.enums import CouponType


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    type: Mapped[CouponType] = mapped_column(SAEnum(CouponType))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # percentage or fixed amount
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    global_usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    product_restrictions: Mapped[list | None] = mapped_column(Text, nullable=True)  # JSON list of product IDs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    usages = relationship("CouponUsage", back_populates="coupon")


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("coupons.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id"), nullable=True)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    coupon = relationship("Coupon", back_populates="usages")
