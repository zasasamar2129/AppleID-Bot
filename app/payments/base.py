from abc import ABC, abstractmethod
from typing import Any

from app.database.models.payment import Payment


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment(self, order_id: int, amount: float, currency: str) -> dict[str, Any]:
        """Create a payment and return external payment info."""
        raise NotImplementedError

    @abstractmethod
    async def verify_payment(self, payment: Payment) -> dict[str, Any]:
        """Verify a payment with the provider. Returns dict with 'paid' boolean."""
        raise NotImplementedError

    @abstractmethod
    async def refund_payment(self, payment: Payment) -> bool:
        """Refund a payment. Returns True if successful."""
        raise NotImplementedError
