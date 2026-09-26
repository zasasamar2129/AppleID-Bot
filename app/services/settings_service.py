from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.settings_repo import SettingsRepository


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.settings_repo = SettingsRepository(session)

    async def get(self, key, default=None):
        return await self.settings_repo.get(key, default)

    async def set(self, key, value, value_type="str", description=None):
        await self.settings_repo.set(key, value, value_type, description)

    @property
    def payment_method_keys(self) -> tuple[str, str, str]:
        return (
            "payment_online_enabled",
            "payment_card_enabled",
            "payment_wallet_enabled",
        )

    async def get_payment_methods(self) -> dict[str, bool]:
        """Return {key: enabled} for each payment method, defaulting to enabled."""
        defaults = {
            "payment_online_enabled": True,
            "payment_card_enabled": True,
            "payment_wallet_enabled": True,
        }
        result = {}
        for key, default in defaults.items():
            val = await self.get(key, default)
            result[key] = bool(val) if val is not None else default
        return result

    async def set_payment_method(self, key: str, enabled: bool) -> None:
        await self.set(key, enabled, value_type="bool")
