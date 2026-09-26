from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def validate_positive_decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text)
        if value > 0:
            return value
    except (InvalidOperation, ValueError):
        pass
    return None


def validate_telegram_id(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    return None


def validate_card_number(text: str) -> bool:
    # Basic validation: 16 digits
    return bool(re.fullmatch(r"\d{16}", text.replace(" ", "")))


def sanitize_text(text: str) -> str:
    return text.strip()[:4000]  # Telegram message limit
