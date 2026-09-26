from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.price_inquiry import PriceInquiry
from app.database.models.unlock_inquiry import UnlockInquiry
from app.database.models.enums import UnlockInquiryStatus
from app.database.repositories.price_inquiry_repo import PriceInquiryRepository
from app.database.repositories.unlock_inquiry_repo import UnlockInquiryRepository


class PriceInquiryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PriceInquiryRepository(session)
        self.unlock_repo = UnlockInquiryRepository(session)

    async def get_active_items(self) -> list[PriceInquiry]:
        return await self.repo.get_active()

    async def get_all_items(self) -> list[PriceInquiry]:
        return await self.repo.get_all()

    async def create_item(self, name_fa: str, name_en: str, price: Decimal, description_fa: str | None = None, description_en: str | None = None, currency: str = "IRR", sort_order: int = 0) -> PriceInquiry:
        data = {
            "name_fa": name_fa,
            "name_en": name_en,
            "price": price,
            "currency": currency,
            "description_fa": description_fa,
            "description_en": description_en,
            "sort_order": sort_order,
        }
        return await self.repo.create(data)

    async def update_item(self, item_id: int, data: dict) -> PriceInquiry | None:
        return await self.repo.update(item_id, data)

    async def delete_item(self, item_id: int) -> None:
        await self.repo.delete(item_id)

    # ---------- Unlock Apple ID inquiries ----------

    async def create_inquiry(self, user_id: int, model: str, apple_id_email: str, customer_phone: str, has_credentials: str) -> UnlockInquiry:
        return await self.unlock_repo.create(
            user_id=user_id,
            model=model,
            apple_id_email=apple_id_email,
            customer_phone=customer_phone,
            has_credentials=has_credentials,
        )

    async def get_user_past_inquiries(self, user_id: int, limit: int = 20) -> list[UnlockInquiry]:
        return await self.unlock_repo.get_by_user(user_id, limit=limit)

    async def get_user_inquiry(self, inquiry_id: int) -> UnlockInquiry | None:
        return await self.unlock_repo.get_by_id(inquiry_id)

    async def get_user_inquiry_by_id(self, inquiry_id: int, user_id: int) -> UnlockInquiry | None:
        item = await self.unlock_repo.get_by_id(inquiry_id)
        if item and item.user_id == user_id:
            return item
        return None

    async def update_inquiry_status(self, inquiry_id: int, status: UnlockInquiryStatus) -> UnlockInquiry | None:
        return await self.unlock_repo.update_status(inquiry_id, status)

    async def get_all_inquiries(self, limit: int = 50) -> list[UnlockInquiry]:
        return await self.unlock_repo.get_all(limit=limit)