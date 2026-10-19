import time
import json
import uuid
from app.core.hmac_auth import generate_hmac_signature, nonce_cache
from tests.conftest import make_hmac_headers


def test_hmac_coordinator_get_success(client):
    headers = make_hmac_headers("GET", "/api/key/verify", b"", client_id="coordinator")
    response = client.get("/api/key/verify", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["client_id"] == "coordinator"
    assert data["role"] == "coordinator"
    assert "write" in data["permissions"]


def test_hmac_engineer_get_success(client):
    headers = make_hmac_headers(
        "GET",
        "/api/key/verify",
        b"",
        client_id="engineer",
        secret="engineer-secret-key-sf-master"
    )
    response = client.get("/api/key/verify", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["client_id"] == "engineer"
    assert data["role"] == "engineer"
    assert data["permissions"] == ["read"]


def test_hmac_engineer_forbidden_on_post(client):
    payload = {"login_url": "https://test.com", "username": "eng@test.com", "password": "pw", "client_id": "cid"}
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = make_hmac_headers(
        "POST",
        "/api/validate-credentials",
        body_bytes,
        client_id="engineer",
        secret="engineer-secret-key-sf-master"
    )
    response = client.post(
        "/api/validate-credentials",
        content=body_bytes,
        headers={"Content-Type": "application/json", **headers}
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_hmac_missing_headers(client):
    response = client.get("/api/key/verify")
    assert response.status_code == 401
    assert "Missing required authentication headers" in response.json()["detail"]


def test_hmac_expired_timestamp(client):
    expired_ts = str(int(time.time()) - 400)  # > 300 seconds ago
    nonce = str(uuid.uuid4())
    sig = generate_hmac_signature("GET", "/api/key/verify", expired_ts, nonce, b"", "coordinator-secret-key-sf-master")
    headers = {
        "X-SF-Signature": sig,
        "X-SF-Timestamp": expired_ts,
        "X-SF-Client-ID": "coordinator",
        "X-SF-Nonce": nonce
    }
    response = client.get("/api/key/verify", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_hmac_replay_attack_rejected(client):
    nonce_cache.clear()
    headers = make_hmac_headers("GET", "/api/key/verify", b"", client_id="coordinator")
    
    # First request succeeds
    first_resp = client.get("/api/key/verify", headers=headers)
    assert first_resp.status_code == 200

    # Second request with identical nonce should be rejected
    second_resp = client.get("/api/key/verify", headers=headers)
    assert second_resp.status_code == 401
    assert "Duplicate nonce detected" in second_resp.json()["detail"]


def test_hmac_invalid_signature(client):
    headers = make_hmac_headers("GET", "/api/key/verify", b"", client_id="coordinator")
    headers["X-SF-Signature"] = "0" * 64  # Wrong signature
    response = client.get("/api/key/verify", headers=headers)
    assert response.status_code == 401
    assert "Invalid HMAC signature" in response.json()["detail"]


def test_hmac_unknown_client_id(client):
    headers = make_hmac_headers("GET", "/api/key/verify", b"", client_id="attacker")
    response = client.get("/api/key/verify", headers=headers)
    assert response.status_code == 401
    assert "Unknown client ID" in response.json()["detail"]
