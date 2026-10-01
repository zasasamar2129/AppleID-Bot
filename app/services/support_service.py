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

    async def reply_admin(
        self, ticket_id: int, admin_id: int | None, message: str
    ) -> SupportMessage:
        """Persist an admin reply.

        ``admin_id`` is the internal admin_users.id, which can be None: the
        IsAdmin filter also admits anyone listed in settings.admin_ids_list, and
        those may have no admin_users row. The reply is still recorded rather
        than dropped, so the conversation stays intact.
        """
        return await self.support_repo.add_message(
            ticket_id, sender_user_id=None, sender_admin_id=admin_id, message=message
        )

    async def get_messages(self, ticket_id: int) -> list[SupportMessage]:
        return await self.support_repo.get_messages(ticket_id)

    async def count_tickets(self, status: SupportStatus | None = None) -> int:
        return await self.support_repo.count_tickets(status)

    async def count_by_status(self) -> dict[SupportStatus, int]:
        return await self.support_repo.count_by_status()

    async def get_all_tickets_paginated(
        self, status: SupportStatus | None = None, limit: int = 10, offset: int = 0
    ) -> list[SupportTicket]:
        return await self.support_repo.get_all_tickets_paginated(status, limit, offset)

    async def get_ticket_with_user(self, ticket_id: int) -> SupportTicket | None:
        return await self.support_repo.get_ticket_with_user(ticket_id)

    async def get_messages_paginated(
        self, ticket_id: int, limit: int = 20, offset: int = 0
    ) -> list[SupportMessage]:
        return await self.support_repo.get_messages_paginated(ticket_id, limit, offset)

    async def count_messages(self, ticket_id: int) -> int:
        return await self.support_repo.count_messages(ticket_id)

    async def get_last_messages(
        self, ticket_ids: list[int]
    ) -> dict[int, SupportMessage]:
        return await self.support_repo.get_last_messages(ticket_ids)
