from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.database.models.payment import Payment
from app.payments.base import PaymentProvider

logger = logging.getLogger(__name__)


class CustomPaymentAPI(PaymentProvider):
    """Adapter for the custom payment API.

    NOTE: The actual API specification has not been provided.
    This class isolates provider-specific code. The methods below
    are placeholders that raise NotImplementedError when called if
    the API is not configured. Implement the actual HTTP calls
    according to the provider's documentation.
    """

    def __init__(self):
        self.base_url = settings.payment_api_base_url
        self.api_key = settings.payment_api_key
        self.api_secret = settings.payment_api_secret

    async def create_payment(self, order_id: int, amount: float, currency: str) -> dict[str, Any]:
        if not settings.is_online_payment_configured:
            raise ValueError("Online payment is not configured")
        # TODO: Implement actual API request based on provider spec
        # Example:
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(f"{self.base_url}/payments", json={...}, headers={...})
        #     response.raise_for_status()
        #     return response.json()
        raise NotImplementedError("Custom payment API contract not implemented. Configure in app/payments/custom_api.py")

    async def verify_payment(self, payment: Payment) -> dict[str, Any]:
        if not settings.is_online_payment_configured:
            raise ValueError("Online payment is not configured")
        # TODO: Implement actual verification API call
        raise NotImplementedError("Custom payment API contract not implemented. Configure in app/payments/custom_api.py")

    async def refund_payment(self, payment: Payment) -> bool:
        if not settings.is_online_payment_configured:
            raise ValueError("Online payment is not configured")
        # TODO: Implement actual refund API call
        raise NotImplementedError("Custom payment API contract not implemented. Configure in app/payments/custom_api.py")
