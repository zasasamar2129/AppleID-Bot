from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.enums import (
    UnlockPaymentStatus,
    UnlockRequestStatus,
    enum_values,
)


class UnlockRequest(Base):
    __tablename__ = "apple_id_unlock_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Device + request fields
    iphone_series: Mapped[str] = mapped_column(String(50))          # internal value: iphone_17 etc
    email_access: Mapped[bool] = mapped_column(Boolean, default=False)
    apple_id_email_encrypted: Mapped[str] = mapped_column(Text)
    apple_id_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    imei: Mapped[str] = mapped_column(String(15))
    other_iphone_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    additional_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)  # customer contact phone

    # Business state
    status: Mapped[UnlockRequestStatus] = mapped_column(
        SAEnum(
            UnlockRequestStatus,
            name="unlockrequeststatus",
            values_callable=enum_values,
        ),
        default=UnlockRequestStatus.SUBMITTED,
        index=True,
    )
    payment_status: Mapped[UnlockPaymentStatus] = mapped_column(
        SAEnum(
            UnlockPaymentStatus,
            name="unlockpaymentstatus",
            values_callable=enum_values,
        ),
        default=UnlockPaymentStatus.NOT_REQUESTED,
    )
    payment_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Admin handling
    admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_users.id"), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="unlock_requests")