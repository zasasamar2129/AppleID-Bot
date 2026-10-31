import logging
import httpx
from bridge_app.config import settings

logger = logging.getLogger(__name__)

class SepClient:
    async def request_token(self, order_id: str, amount_rial: int, redirect_url: str) -> dict:
        terminal_id = settings.sep_terminal_id or settings.sep_merchant_id
        payload = {
            "Action": "Token",
            "Amount": amount_rial,
            "ResNum": order_id,
            "TerminalId": terminal_id,
            "RedirectURL": redirect_url,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            try:
                response = await client.post(settings.sep_token_api_url, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                logger.error("SEP token request timed out")
                raise RuntimeError("SEP token request timed out") from exc
            except httpx.HTTPError as exc:
                logger.error(f"SEP token HTTP error: {type(exc).__name__}")
                raise RuntimeError(f"SEP token request failed: {type(exc).__name__}") from exc

        if str(data.get("status")) == "1" and data.get("token"):
            return {
                "token": data["token"],
                "url": settings.sep_payment_url,
            }

        logger.warning(f"SEP rejected token request: {data}")
        raise ValueError(f"SEP rejected payment: {data.get('errorDesc') or data.get('errorCode') or 'Unknown Error'}")

    async def verify_transaction(self, ref_num: str, terminal_id: str) -> dict:
        payload = {
            "RefNum": ref_num,
            "TerminalNumber": terminal_id,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            try:
                response = await client.post(settings.sep_verify_api_url, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                logger.error("SEP verify request timed out")
                raise RuntimeError("SEP verify request timed out") from exc
            except httpx.HTTPError as exc:
                logger.error(f"SEP verify HTTP error: {type(exc).__name__}")
                raise RuntimeError(f"SEP verify request failed: {type(exc).__name__}") from exc

        if data.get("ResultCode") == 0:
            detail = data.get("TransactionDetail") or {}
            return {
                "paid": True,
                "external_id": detail.get("RefNum") or ref_num,
                "amount": detail.get("Amount"),
            }

        logger.info(f"SEP verification declined: {data}")
        return {
            "paid": False,
            "external_id": None,
            "amount": None,
        }
