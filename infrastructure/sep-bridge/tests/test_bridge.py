from fastapi.testclient import TestClient

from bridge_app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_missing_header():
    """No Authorization header at all must be rejected before any SEP call."""
    response = client.post(
        "/api/v1/sep/token",
        json={"order_id": "1", "amount": 1000, "redirect_url": "https://example.com"},
    )
    assert response.status_code in (401, 403)


def test_auth_invalid_token():
    response = client.post(
        "/api/v1/sep/token",
        json={"order_id": "1", "amount": 1000, "redirect_url": "https://example.com"},
        headers={"Authorization": "Bearer wrong_token"},
    )
    assert response.status_code == 401


def test_valid_token_bad_payload_is_validation_error():
    """Auth passes, then schema validation rejects — never a crash, never a SEP call."""
    response = client.post(
        "/api/v1/sep/token",
        json={"order_id": "1"},
        headers={"Authorization": "Bearer test_secret_key"},
    )
    assert response.status_code == 422
