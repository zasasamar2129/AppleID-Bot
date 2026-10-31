"""
Saman Bank (SEP) payment provider adapter.

If PAYMENT_BRIDGE_URL is configured, calls the dedicated Iran SEP Bridge API.
Otherwise, communicates directly with SEP (when running in Iran or with direct access).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.database.models.payment import Payment
from app.payments.base import PaymentProvider
from app.utils.money import to_gateway_amount

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_API_URL = "https://sep.shaparak.ir/OnlinePG/SendToken"
DEFAULT_PAYMENT_URL = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
DEFAULT_VERIFY_API_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"

REQUEST_TIMEOUT_SECONDS = 15.0


class SepGatewayError(Exception):
    """Gateway rejected or mis-answered a request. Carries no credentials."""


class SepPaymentProvider(PaymentProvider):
    def __init__(self) -> None:
        self.merchant_code: str = settings.sep_merchant_id or ""
        self.terminal_code: str = settings.sep_terminal_id or ""
        self.callback_url: str = settings.sep_callback_url or ""

        self.token_api_url: str = settings.sep_api_url or DEFAULT_TOKEN_API_URL
        self.payment_url: str = settings.sep_payment_url or DEFAULT_PAYMENT_URL
        self.verify_api_url: str = settings.sep_verify_url or DEFAULT_VERIFY_API_URL

        # Bridge Settings
        self.bridge_url: str | None = settings.payment_bridge_url
        self.bridge_api_key: str | None = settings.payment_bridge_api_key

    async def create_payment(self, order_id: int, amount: float, currency: str) -> dict[str, Any]:
        """Request a payment token for ``amount`` (Toman) under ``order_id``."""
        if not settings.sep_enabled:
            raise SepGatewayError("SEP payment is not enabled")

        amount_rial = to_gateway_amount(amount)

        # 1. Use Iran Bridge if configured
        if self.bridge_url and self.bridge_api_key:
            headers = {"Authorization": f"Bearer {self.bridge_api_key}"}
            payload = {
                "order_id": str(order_id),
                "amount": amount_rial,
                "redirect_url": self.callback_url,
            }
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        f"{self.bridge_url.rstrip('/')}/api/v1/sep/token",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return {
                        "token": data["token"],
                        "url": data["url"],
                        "gateway_amount": amount_rial,
                    }
            except httpx.HTTPStatusError as exc:
                logger.error(f"Bridge HTTP error: {exc.response.status_code} - {exc.response.text}")
                raise SepGatewayError(f"Bridge error: {exc.response.status_code}") from exc
            except Exception as exc:
                logger.error(f"Bridge connection error: {exc}")
                raise SepGatewayError("Bridge connection failed") from exc

        # 2. Direct SEP Connection fallback
        if not self.merchant_code or not self.callback_url:
            raise SepGatewayError("SEP is not fully configured")

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    self.token_api_url,
                    json={
                        "Action": "Token",
                        "Amount": amount_rial,
                        "ResNum": str(order_id),
                        "TerminalId": self.merchant_code,
                        "RedirectURL": self.callback_url,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise SepGatewayError("SEP token request timed out") from exc
        except httpx.HTTPError as exc:
            raise SepGatewayError(f"SEP token request failed: {type(exc).__name__}") from exc

        if str(data.get("status")) == "1" and data.get("token"):
            return {
                "token": data["token"],
                "url": self.payment_url,
                "gateway_amount": amount_rial,
            }

        raise SepGatewayError(f"SEP rejected payment: {data.get('errorDesc') or 'unknown error'}")

    async def verify_payment(self, payment: Payment) -> dict[str, Any]:
        """Server-side verification."""
        if not settings.sep_enabled:
            raise SepGatewayError("SEP payment is not enabled")

        ref_num = payment.reference_number or payment.transaction_id
        if not ref_num:
            logger.warning("SEP verify skipped: payment %s has no RefNum", payment.id)
            return {"paid": False, "reason": "missing_refnum"}

        # 1. Use Iran Bridge if configured
        if self.bridge_url and self.bridge_api_key:
            headers = {"Authorization": f"Bearer {self.bridge_api_key}"}
            payload = {
                "ref_num": str(ref_num),
                "terminal_id": self.merchant_code or "0",
            }
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        f"{self.bridge_url.rstrip('/')}/api/v1/sep/verify",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return {
                        "paid": data["paid"],
                        "external_id": data.get("external_id"),
                        "verified_amount": data.get("amount"),
                    }
            except Exception as exc:
                logger.error(f"Bridge verification failed: {exc}")
                raise SepGatewayError("Bridge verify failed") from exc

        # 2. Direct SEP Verification fallback
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    self.verify_api_url,
                    json={
                        "RefNum": ref_num,
                        "TerminalNumber": self.merchant_code,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise SepGatewayError(f"SEP verify request failed: {exc}") from exc

        if data.get("ResultCode") == 0:
            detail = data.get("TransactionDetail") or {}
            return {
                "paid": True,
                "external_id": detail.get("RefNum") or ref_num,
                "verified_amount": detail.get("Amount"),
            }

        return {"paid": False, "reason": str(data.get("ResultCode"))}

    async def refund_payment(self, payment: Payment) -> bool:
        raise NotImplementedError("SEP reversal is not implemented for this terminal.")
