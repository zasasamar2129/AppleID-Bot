from __future__ import annotations

import secrets
import string
from decimal import Decimal, InvalidOperation


def format_price(amount, lang: str = "fa") -> str:
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        amount = Decimal(0)
    if amount == amount.to_integral_value():
        formatted = f"{amount:,.0f}"
    else:
        formatted = f"{amount:,.2f}"
    if lang == "fa":
        return f"{formatted} تومان"
    else:
        return f"{formatted} Toman"


def generate_tracking_id(length: int = 8) -> str:
    """Generate a short, human-readable tracking ID for card-to-card payments.

    e.g. AP-A1B2C3D4. Uses secrets to avoid predictable/guessable IDs.
    """
    alphabet = string.ascii_uppercase + string.digits
    # Omit confusing chars (0/O, 1/I) for readability.
    alphabet = "".join(c for c in alphabet if c not in "0O1I")
    return "AP-" + "".join(secrets.choice(alphabet) for _ in range(length))
