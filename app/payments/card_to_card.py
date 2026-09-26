from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardToCardDetails:
    card_number: str
    holder: str
    bank: str

    @classmethod
    def from_settings(cls):
        from app.config import settings
        return cls(
            card_number=settings.card_to_card_number or "",
            holder=settings.card_to_card_holder or "",
            bank=settings.card_to_card_bank or "",
        )
