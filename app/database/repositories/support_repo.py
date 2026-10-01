from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.enums import SupportCategory, SupportStatus
from app.database.models.support import SupportMessage, SupportTicket


class SupportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ticket(self, user_id: int, subject: str, category: SupportCategory) -> SupportTicket:
        ticket = SupportTicket(
            user_id=user_id,
            subject=subject,
            category=category,
            status=SupportStatus.OPEN,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        return await self.session.get(SupportTicket, ticket_id)

    async def get_user_tickets(self, user_id: int) -> list[SupportTicket]:
        stmt = select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_tickets(self, status: SupportStatus | None = None) -> list[SupportTicket]:
        stmt = select(SupportTicket)
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        stmt = stmt.order_by(SupportTicket.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_tickets(self, status: SupportStatus | None = None) -> int:
        stmt = select(func.count()).select_from(SupportTicket)
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_status(self) -> dict[SupportStatus, int]:
        """Ticket counts per status, for the admin filter tabs."""
        stmt = select(SupportTicket.status, func.count()).group_by(SupportTicket.status)
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def get_all_tickets_paginated(
        self,
        status: SupportStatus | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[SupportTicket]:
        """One page of tickets, newest activity first.

        ``selectinload(SupportTicket.user)`` is required: the admin list renders
        the customer's name, and touching a lazy-loaded relationship outside an
        awaited query raises MissingGreenlet on the event loop.
        """
        stmt = select(SupportTicket).options(selectinload(SupportTicket.user))
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        stmt = stmt.order_by(SupportTicket.updated_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_ticket_with_user(self, ticket_id: int) -> SupportTicket | None:
        """Fetch a ticket with its customer eagerly loaded."""
        stmt = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.user))
            .where(SupportTicket.id == ticket_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_ticket_status(self, ticket_id: int, status: SupportStatus) -> None:
        ticket = await self.get_ticket(ticket_id)
        if ticket:
            ticket.status = status
            ticket.updated_at = datetime.utcnow()
            await self.session.commit()

    async def assign_admin(self, ticket_id: int, admin_id: int) -> None:
        ticket = await self.get_ticket(ticket_id)
        if ticket:
            ticket.admin_id = admin_id
            ticket.updated_at = datetime.utcnow()
            await self.session.commit()

    async def add_message(self, ticket_id: int, sender_user_id: int | None, sender_admin_id: int | None, message: str) -> SupportMessage:
        msg = SupportMessage(
            ticket_id=ticket_id,
            sender_user_id=sender_user_id,
            sender_admin_id=sender_admin_id,
            message=message,
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        # update ticket updated_at
        ticket = await self.get_ticket(ticket_id)
        if ticket:
            ticket.updated_at = datetime.utcnow()
            await self.session.commit()
        return msg

    async def get_messages(self, ticket_id: int) -> list[SupportMessage]:
        stmt = select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_messages_paginated(
        self, ticket_id: int, limit: int = 20, offset: int = 0
    ) -> list[SupportMessage]:
        """One page of a conversation, oldest first.

        Pages are needed because a long thread can exceed Telegram's
        4096-character message limit in a single render.
        """
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_messages(self, ticket_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_last_messages(
        self, ticket_ids: list[int]
    ) -> dict[int, SupportMessage]:
        """Latest message per ticket, for the admin list preview.

        One query for the whole page instead of N per ticket.
        """
        if not ticket_ids:
            return {}
        subquery = (
            select(SupportMessage.ticket_id, func.max(SupportMessage.created_at).label("max_created"))
            .where(SupportMessage.ticket_id.in_(ticket_ids))
            .group_by(SupportMessage.ticket_id)
            .subquery()
        )
        stmt = (
            select(SupportMessage)
            .join(
                subquery,
                (SupportMessage.ticket_id == subquery.c.ticket_id)
                & (SupportMessage.created_at == subquery.c.max_created),
            )
            .where(SupportMessage.ticket_id.in_(ticket_ids))
        )
        result = await self.session.execute(stmt)
        return {msg.ticket_id: msg for msg in result.scalars().all()}
