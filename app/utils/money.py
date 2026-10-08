"""Central money conversion.

The bot's money model stores and displays **Toman** (see
``app.utils.formatting.format_price``). Iranian gateways, Saman/SEP included,
take **Rial**.

Every Rial conversion MUST go through this module — never inline ``* 10``.

All amounts are ``Decimal``/``int``. No floats.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union

__all__ = [
    "RIAL_PER_TOMAN",
    "toman_to_rial",
    "rial_to_toman",
    "to_gateway_amount",
    "parse_amount",
    "MoneyLike",
]

# Anything numeric the bot may hand us: a Decimal from the DB, an int from
# settings, or a string typed by a user. Never a float in real data, but
# accepting it here keeps callers honest instead of crashing.
MoneyLike = Union[str, int, float, Decimal]

# 1 Toman = 10 Rial. Fixed by Iranian currency law; not configurable.
RIAL_PER_TOMAN = 10


def toman_to_rial(toman: MoneyLike) -> int:
    """Toman -> Rial as an ``int`` (what the gateway API expects)."""
    return int((Decimal(str(toman)) * RIAL_PER_TOMAN).to_integral_value(rounding=ROUND_HALF_UP))


def rial_to_toman(rial: MoneyLike) -> Decimal:
    """Rial -> Toman, preserving sub-Toman digits instead of truncating."""
    try:
        value = Decimal(str(rial))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    if not value.is_finite():
        return Decimal(0)
    return (value / Decimal(RIAL_PER_TOMAN)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_gateway_amount(amount_toman: MoneyLike) -> int:
    """Amount in the bot's Toman unit -> integer Rial for the gateway.

    Rejects non-positive and non-finite input: the gateway rejects them
    anyway, and failing here keeps a bogus payment from ever being created.
    """
    value = _to_decimal(amount_toman, "amount")
    if value <= 0:
        raise ValueError(f"amount must be positive, got {amount_toman!r}")
    return toman_to_rial(value)


def parse_amount(raw: MoneyLike) -> Decimal:
    """Parse user/API input into a ``Decimal``. Raises ``ValueError`` if invalid."""
    return _to_decimal(raw, "amount")


def _to_decimal(raw: object, label: str) -> Decimal:
    try:
        value = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"invalid {label}: {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"invalid {label}: {raw!r}")
    return value
