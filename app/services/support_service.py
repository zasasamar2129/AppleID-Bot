from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import SupportCategory, SupportStatus
from app.database.models.support import SupportMessage, SupportTicket
from app.database.repositories.support_repo import SupportRepository


class SupportService:
    def __init__(self, session: AsyncSession):
        self.support_repo = SupportRepository(session)

    async def create_ticket(self, user_id: int, subject: str, category: SupportCategory) -> SupportTicket:
        return await self.support_repo.create_ticket(user_id, subject, category)

    async def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        return await self.support_repo.get_ticket(ticket_id)

    async def get_user_tickets(self, user_id: int) -> list[SupportTicket]:
        return await self.support_repo.get_user_tickets(user_id)

    async def get_all_tickets(self, status: SupportStatus | None = None) -> list[SupportTicket]:
        return await self.support_repo.get_all_tickets(status)

    async def update_status(self, ticket_id: int, status: SupportStatus) -> None:
        await self.support_repo.update_ticket_status(ticket_id, status)

    async def assign_admin(self, ticket_id: int, admin_id: int) -> None:
        await self.support_repo.assign_admin(ticket_id, admin_id)

    async def reply_user(self, ticket_id: int, user_id: int, message: str) -> SupportMessage:
        return await self.support_repo.add_message(ticket_id, sender_user_id=user_id, sender_admin_id=None, message=message)

    async def reply_admin(self, ticket_id: int, admin_id: int, message: str) -> SupportMessage:
        return await self.support_repo.add_message(ticket_id, sender_user_id=None, sender_admin_id=admin_id, message=message)

    async def get_messages(self, ticket_id: int) -> list[SupportMessage]:
        return await self.support_repo.get_messages(ticket_id)
