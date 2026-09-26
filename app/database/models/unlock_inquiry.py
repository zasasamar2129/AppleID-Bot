from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.enums import UnlockInquiryStatus, enum_values


class UnlockInquiry(Base):
    __tablename__ = "unlock_inquiries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    model: Mapped[str] = mapped_column(String(255))
    apple_id_email: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(100))
    has_credentials: Mapped[str] = mapped_column(String(20))  # 'yes' or 'no'

    status: Mapped[UnlockInquiryStatus] = mapped_column(
        SAEnum(
            UnlockInquiryStatus,
            name="unlockinquirystatus",
            values_callable=enum_values,
        ),
        default=UnlockInquiryStatus.PENDING,
    )

    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="unlock_inquiries")