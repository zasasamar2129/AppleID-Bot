from __future__ import annotations

from app.config import settings
from app.payments.base import PaymentProvider
from app.payments.custom_api import CustomPaymentAPI
from app.payments.sep import SepPaymentProvider


def get_online_payment_provider() -> PaymentProvider:
    """Pick the configured online provider.

    SEP wins when enabled, because a half-configured custom API must not
    silently take over real payments.
    """
    if settings.sep_enabled:
        return SepPaymentProvider()
    return CustomPaymentAPI()


# Kept as an alias so existing imports keep working.
OnlinePaymentProvider = get_online_payment_provider
