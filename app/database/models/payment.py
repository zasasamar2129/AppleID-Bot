from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.enums import PaymentMethod, PaymentStatus


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # order_id is nullable because wallet top-up payments have no associated order.
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id"), index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50), default="custom_api")
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name='paymentmethod_pay'))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="IRR")
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, index=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_type: Mapped[str | None] = mapped_column(String(20), nullable=True)      # 'photo' or 'text'
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_users.id"), nullable=True)

    # --- SEP / online gateway lifecycle ---------------------------------
    # ResNum we generate and send to the gateway; unique per payment attempt.
    tracking_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    # Token returned by the gateway's SendToken call. Required to open the
    # payment page; NOT proof of payment.
    authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # RefNum reported by the bank on return. Required for VerifyTransaction.
    reference_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Amount actually sent to the gateway, in Rial (integer string form).
    gateway_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-form gateway diagnostics. Never stores credentials.
    # Column is named "metadata" (reserved by SQLAlchemy's declarative API as a
    # class attribute, hence the trailing underscore).
    metadata_: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")
    user = relationship("User", back_populates="payments")
