from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.settings import Setting


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: Any = None) -> Any:
        stmt = select(Setting).where(Setting.key == key)
        result = await self.session.execute(stmt)
        setting = result.scalar_one_or_none()
        if not setting:
            return default
        if setting.value_type == "int":
            return int(setting.value)
        elif setting.value_type == "bool":
            return setting.value.lower() in ("true", "1", "yes")
        elif setting.value_type == "json":
            try:
                return json.loads(setting.value)
            except:
                return default
        else:
            return setting.value

    async def set(self, key: str, value: Any, value_type: str = "str", description: str | None = None) -> None:
        stmt = select(Setting).where(Setting.key == key)
        result = await self.session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = str(value)
            setting.value_type = value_type
            if description:
                setting.description = description
            setting.updated_at = datetime.utcnow()
        else:
            setting = Setting(
                key=key,
                value=str(value),
                value_type=value_type,
                description=description,
            )
            self.session.add(setting)
        await self.session.commit()

    async def get_all(self) -> list[Setting]:
        stmt = select(Setting).order_by(Setting.key)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
