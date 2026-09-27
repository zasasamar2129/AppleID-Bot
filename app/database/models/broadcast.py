from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_users.id"))
    content_type: Mapped[str] = mapped_column(String(20))  # text, photo, video, document
    content: Mapped[str] = mapped_column(Text)  # text or file_id
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    inline_buttons_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    audience_filter: Mapped[str] = mapped_column(Text)  # JSON criteria
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, in_progress, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BroadcastReceipt(Base):
    __tablename__ = "broadcast_receipts"
    # One receipt per (broadcast, user): this is what makes a resumed
    # broadcast skip users it already delivered to, and what makes a duplicate
    # run a no-op instead of a duplicate message.
    __table_args__ = (
        UniqueConstraint(
            "broadcast_id", "user_id", name="uq_broadcast_receipts_broadcast_user"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("broadcasts.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # sent, failed, blocked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
