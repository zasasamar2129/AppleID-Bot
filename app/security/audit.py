from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.admin_repo import AdminRepository
from app.database.repositories.audit_repo import AuditRepository


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditRepository(session)
        self.admin_repo = AdminRepository(session)

    async def log(self, admin_telegram_id: int | None, action: str, target_type: str, target_id: str | None = None, metadata: dict | None = None):
        admin_id = None
        if admin_telegram_id:
            admin = await self.admin_repo.get_by_telegram_id(admin_telegram_id)
            if admin:
                admin_id = admin.id

        safe_metadata = None
        if metadata:
            safe_metadata = {k: v for k, v in metadata.items() if not any(secret in k.lower() for secret in ["password", "token", "secret", "key", "card"])}
        await self.repo.log(admin_id=admin_id, action=action, target_type=target_type, target_id=target_id, metadata=safe_metadata)
