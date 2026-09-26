from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    reward_given: Mapped[bool] = mapped_column(default=False)
    reward_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    referrer = relationship("User", foreign_keys=[referrer_id], backref="referrals_made")
    referred_user = relationship("User", foreign_keys=[referred_user_id], backref="referral_as_referred")
