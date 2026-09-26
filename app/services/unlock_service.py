from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.enums import UnlockPaymentStatus, UnlockRequestStatus
from app.database.models.unlock_request import UnlockRequest
from app.database.repositories.unlock_request_repo import UnlockRequestRepository
from app.security.encryption import EncryptionService

logger = logging.getLogger(__name__)


# Central iphone series definitions. Internal value -> localized keys.
IPHONE_SERIES_ORDER = [
    "iphone_17",
    "iphone_16",
    "iphone_15",
    "iphone_14",
    "iphone_13",
    "iphone_12",
    "iphone_11",
    "iphone_x_or_older",
]


class UnlockService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UnlockRequestRepository(session)
        self.encryption = EncryptionService(settings.encryption_key)

    # ---------- Sensitive data handling ----------

    def _encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.encryption.encrypt(value)

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self.encryption.decrypt(value)
        except Exception as e:
            logger.error(f"Failed to decrypt unlock field: {type(e).__name__}")
            return None

    # ---------- Create ----------

    async def create_request(
        self,
        user_id: int,
        telegram_user_id: int,
        iphone_series: str,
        email_access: bool,
        apple_id_email: str,
        apple_id_password: str | None,
        imei: str,
        other_iphone_locked: bool,
        additional_information: str | None,
        phone_number: str | None = None,
    ) -> UnlockRequest:
        return await self.repo.create({
            "user_id": user_id,
            "telegram_user_id": telegram_user_id,
            "iphone_series": iphone_series,
            "email_access": email_access,
            "apple_id_email_encrypted": self._encrypt(apple_id_email) or "",
            "apple_id_password_encrypted": self._encrypt(apple_id_password),
            "imei": imei,
            "other_iphone_locked": other_iphone_locked,
            "additional_information": additional_information,
            "phone_number": phone_number,
            "status": UnlockRequestStatus.SUBMITTED,
            "payment_status": UnlockPaymentStatus.NOT_REQUESTED,
        })

    # ---------- Read ----------

    async def get_request(self, request_id: int) -> UnlockRequest | None:
        return await self.repo.get_by_id(request_id)

    async def get_requests_for_user(self, user_id: int, limit: int = 20) -> list[UnlockRequest]:
        return await self.repo.get_by_user(user_id, limit=limit)

    async def get_all_requests(self, limit: int = 50, offset: int = 0) -> list[UnlockRequest]:
        return await self.repo.get_all(limit=limit, offset=offset)

    async def get_by_status(self, status: UnlockRequestStatus, limit: int = 50) -> list[UnlockRequest]:
        return await self.repo.get_by_status(status, limit=limit)

    # ---------- Decrypted access (admin only) ----------

    def get_email(self, req: UnlockRequest) -> str | None:
        return self._decrypt(req.apple_id_email_encrypted)

    def get_password(self, req: UnlockRequest) -> str | None:
        return self._decrypt(req.apple_id_password_encrypted)

    # ---------- Admin operations ----------

    async def request_payment(self, request_id: int, amount: float, admin_id: int) -> UnlockRequest | None:
        """Transition to PAYMENT_REQUESTED + payment_status=REQUESTED."""
        req = await self.repo.get_by_id(request_id)
        if not req:
            return None
        # Idempotency: if already requested/pending/paid, do not request again.
        if req.payment_status in (UnlockPaymentStatus.REQUESTED, UnlockPaymentStatus.PENDING, UnlockPaymentStatus.PAID):
            return req
        return await self.repo.update(request_id, {
            "status": UnlockRequestStatus.PAYMENT_REQUESTED,
            "payment_status": UnlockPaymentStatus.REQUESTED,
            "payment_amount": amount,
            "admin_id": admin_id,
        })

    async def set_status(self, request_id: int, status: UnlockRequestStatus, admin_id: int, note: str | None = None) -> UnlockRequest | None:
        data: dict = {"status": status, "admin_id": admin_id}
        if note:
            data["admin_notes"] = note
        return await self.repo.update(request_id, data)

    async def add_note(self, request_id: int, note: str, admin_id: int) -> UnlockRequest | None:
        return await self.repo.update(request_id, {"admin_notes": note, "admin_id": admin_id})

    async def complete(self, request_id: int, admin_id: int) -> UnlockRequest | None:
        return await self.repo.update_status(request_id, UnlockRequestStatus.COMPLETED)

    async def reject(self, request_id: int, admin_id: int, reason: str | None = None) -> UnlockRequest | None:
        data: dict = {"status": UnlockRequestStatus.REJECTED, "admin_id": admin_id}
        if reason:
            data["admin_notes"] = reason
        return await self.repo.update(request_id, data)