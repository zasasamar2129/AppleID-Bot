from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
