"""
Saman Bank (SEP) payment provider.

Endpoints and field names below are taken from the SEP implementation in
``az-iranian-bank-gateways`` (``azbankgateways/banks/sep.py``), which is the
reference the project was asked to follow. Nothing here is invented; the
endpoint URLs are overridable via settings because Saman has documented more
than one spelling of the same host path over time.

Flow:
  1. SendToken   POST -> ``{"status": "1", "token": "..."}``
  2. Redirect    GET  -> SEP payment page (``Token`` query param)
  3. Return      GET  -> ``SEP_CALLBACK_URL`` with ResNum/Token/State/RefNum/TRACENO
  4. Verify      POST -> ``{"ResultCode": 0}`` on success

A token is not proof of payment. Only step 4 is.
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

# Defaults mirror the reference package. Override via settings if Saman gives
# you a different host/path for your terminal.
DEFAULT_TOKEN_API_URL = "https://sep.shaparak.ir/OnlinePG/SendToken"
DEFAULT_PAYMENT_URL = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
DEFAULT_VERIFY_API_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"

REQUEST_TIMEOUT_SECONDS = 15.0


class SepGatewayError(Exception):
    """Gateway rejected or mis-answered a request. Carries no credentials."""


class SepPaymentProvider(PaymentProvider):
    def __init__(self) -> None:
        # Saman's "TerminalId" field on SendToken carries the merchant code.
        self.merchant_code: str = settings.sep_merchant_id or ""
        self.terminal_code: str = settings.sep_terminal_id or ""
        self.callback_url: str = settings.sep_callback_url or ""

        self.token_api_url: str = settings.sep_api_url or DEFAULT_TOKEN_API_URL
        self.payment_url: str = settings.sep_payment_url or DEFAULT_PAYMENT_URL
        self.verify_api_url: str = settings.sep_verify_url or DEFAULT_VERIFY_API_URL

    async def create_payment(self, order_id: int, amount: float, currency: str) -> dict[str, Any]:
        """Request a payment token for ``amount`` (Toman) under ``order_id``.

        ``order_id`` here is actually the caller's ResNum; the payment service
        passes the payment's own tracking code so a retry gets a new one.

        Raises ``SepGatewayError`` when the gateway answers but refuses, and
        propagates transport errors for the caller to classify as unknown.
        """
        if not settings.sep_enabled:
            raise SepGatewayError("SEP payment is not enabled")
        if not self.merchant_code or not self.callback_url:
            raise SepGatewayError("SEP is not fully configured")

        # Bot stores Toman; Saman takes Rial.
        amount_rial = to_gateway_amount(amount)

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
            # The request may have reached Saman. Do NOT let the caller assume
            # failure — surface it so the payment stays recoverable.
            raise SepGatewayError("SEP token request timed out") from exc
        except httpx.HTTPError as exc:
            raise SepGatewayError(f"SEP token request failed: {type(exc).__name__}") from exc
        except ValueError as exc:
            raise SepGatewayError("SEP returned a non-JSON response") from exc

        if str(data.get("status")) == "1" and data.get("token"):
            return {
                "token": data["token"],
                "url": self.payment_url,
                "gateway_amount": amount_rial,
            }

        # Log the code only — errorDesc can echo request details.
        logger.warning(
            "SEP rejected token request status=%s code=%s",
            data.get("status"),
            data.get("errorCode"),
        )
        raise SepGatewayError(f"SEP rejected payment: {data.get('errorDesc') or data.get('errorCode') or 'unknown error'}")

    async def verify_payment(self, payment: Payment) -> dict[str, Any]:
        """Server-side verification. This is the only proof of payment.

        Requires ``payment.reference_number`` (RefNum), which only the bank's
        return leg supplies. Without it we cannot verify, so we return
        ``paid=False`` rather than guessing.
        """
        if not settings.sep_enabled:
            raise SepGatewayError("SEP payment is not enabled")

        ref_num = payment.reference_number or payment.transaction_id
        if not ref_num:
            logger.warning("SEP verify skipped: payment %s has no RefNum", payment.id)
            return {"paid": False, "reason": "missing_refnum"}

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
        except httpx.TimeoutException as exc:
            raise SepGatewayError("SEP verify request timed out") from exc
        except httpx.HTTPError as exc:
            raise SepGatewayError(f"SEP verify request failed: {type(exc).__name__}") from exc
        except ValueError as exc:
            raise SepGatewayError("SEP returned a non-JSON response") from exc

        if data.get("ResultCode") == 0:
            detail = data.get("TransactionDetail") or {}
            return {
                "paid": True,
                "external_id": detail.get("RefNum") or ref_num,
                "verified_amount": detail.get("Amount"),
            }

        logger.info(
            "SEP verification declined payment=%s ResultCode=%s",
            payment.id,
            data.get("ResultCode"),
        )
        return {
            "paid": False,
            "reason": str(data.get("ResultCode")),
            "error": data.get("ErrorMessage"),
        }

    async def refund_payment(self, payment: Payment) -> bool:
        raise NotImplementedError("SEP reversal is not implemented for this terminal.")
