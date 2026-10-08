"""NL application -> Iran SEP Bridge client behaviour.

Mocks the bridge at the HTTP boundary; never makes a real payment request.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.payments.sep import SepGatewayError, SepPaymentProvider

BRIDGE_URL = "http://10.0.0.5:8443"


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://bridge.local")
            response = httpx.Response(self.status_code, request=request, json=self._payload)
            raise httpx.HTTPStatusError("upstream error", request=request, response=response)

    def json(self):
        return self._payload


@pytest.fixture
def bridge_config(monkeypatch):
    monkeypatch.setattr(settings, "sep_enabled", True)
    monkeypatch.setattr(settings, "sep_merchant_id", "12345")
    monkeypatch.setattr(settings, "sep_callback_url", "https://example.com/cb")
    monkeypatch.setattr(settings, "payment_bridge_url", BRIDGE_URL)
    monkeypatch.setattr(settings, "payment_bridge_api_key", "secret-key")
    return settings


def _patch_client(monkeypatch, response):
    """Force httpx.AsyncClient.post to return ``response`` and record the call."""
    recorded: dict = {"calls": 0}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None, **kw):
            recorded["calls"] += 1
            recorded["url"] = url
            recorded["json"] = json
            recorded["headers"] = headers
            return _FakeResponse(response) if isinstance(response, dict) else response

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return recorded


class _Payment:
    def __init__(self, ref_num=None, token=None, payment_id=1):
        self.id = payment_id
        self.reference_number = ref_num
        self.transaction_id = token


def test_token_request_targets_bridge_and_sends_auth(bridge_config, monkeypatch):
    recorded = _patch_client(monkeypatch, {"token": "abc", "url": "https://sep/PG"})

    provider = SepPaymentProvider()
    out = asyncio.run(provider.create_payment(order_id=7, amount=1000, currency="IRR"))

    assert recorded["url"] == f"{BRIDGE_URL}/api/v1/sep/token"
    assert recorded["headers"]["Authorization"] == "Bearer secret-key"
    # 1000 Toman -> 10000 Rial
    assert recorded["json"]["amount"] == 10000
    assert recorded["json"]["order_id"] == "7"
    assert out["token"] == "abc"
    assert out["gateway_amount"] == 10000


def test_verify_uses_bridge_and_maps_paid_flag(bridge_config, monkeypatch):
    recorded = _patch_client(
        monkeypatch, {"paid": True, "external_id": "R1", "amount": 10000}
    )

    provider = SepPaymentProvider()
    out = asyncio.run(provider.verify_payment(_Payment(ref_num="R1")))

    assert recorded["url"] == f"{BRIDGE_URL}/api/v1/sep/verify"
    assert recorded["json"] == {"ref_num": "R1", "terminal_id": "12345"}
    assert out["paid"] is True
    assert out["verified_amount"] == 10000


def test_verify_without_refnum_never_calls_bridge(bridge_config, monkeypatch):
    recorded = _patch_client(monkeypatch, {"paid": True})

    provider = SepPaymentProvider()
    out = asyncio.run(provider.verify_payment(_Payment()))

    assert recorded["calls"] == 0  # no HTTP call at all
    assert out == {"paid": False, "reason": "missing_refnum"}


def test_bridge_rejection_maps_to_paid_false(bridge_config, monkeypatch):
    _patch_client(monkeypatch, {"paid": False, "external_id": None, "amount": None})

    provider = SepPaymentProvider()
    out = asyncio.run(provider.verify_payment(_Payment(ref_num="R1")))

    assert out["paid"] is False


def test_bridge_http_error_raises_sepgatewayerror(bridge_config, monkeypatch):
    _patch_client(monkeypatch, _FakeResponse({"detail": "nope"}, status_code=500))

    provider = SepPaymentProvider()
    with pytest.raises(SepGatewayError):
        asyncio.run(provider.create_payment(order_id=7, amount=1000, currency="IRR"))


def test_bridge_connection_failure_raises_sepgatewayerror(bridge_config, monkeypatch):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    provider = SepPaymentProvider()
    with pytest.raises(SepGatewayError):
        asyncio.run(provider.create_payment(order_id=7, amount=1000, currency="IRR"))


def test_nl_holds_only_bridge_credentials(bridge_config):
    """SEP merchant/terminal stay on the Iran VPS; NL holds URL + API key only."""
    provider = SepPaymentProvider()
    assert provider.bridge_url == BRIDGE_URL
    assert provider.bridge_api_key == "secret-key"
    # Direct SEP URLs exist but are unused when a bridge is configured.
    assert provider.token_api_url.startswith("https://sep.shaparak.ir/")
