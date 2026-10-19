from app.services.audit import audit_service
from app.models.audit import AuditLog
from tests.conftest import make_hmac_headers


def test_audit_service_write_and_query(db_session, client):
    # Create audit logs
    entry_id = audit_service.write_audit(
        event_category="SALESFORCE_AUTH",
        event_type="TOKEN_GRANTED",
        organization_id="00DTest123",
        actor_client_id="coordinator",
        actor_role="coordinator",
        outcome="SUCCESS",
        endpoint="/api/validate-credentials",
        http_method="POST",
        status_code=200,
        extra_metadata={"flow": "password"},
        db=db_session
    )
    assert entry_id is not None

    # Query via API with HMAC headers
    headers = make_hmac_headers("GET", "/api/audit/logs", b"", client_id="coordinator")
    response = client.get("/api/audit/logs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    found = any(item["id"] == entry_id for item in data["items"])
    assert found is True


def test_audit_stats_endpoint(db_session, client):
    # Ensure at least one entry exists
    audit_service.write_audit(
        event_category="SYSTEM",
        event_type="STARTUP",
        outcome="SUCCESS",
        db=db_session
    )

    headers = make_hmac_headers("GET", "/api/audit/stats", b"", client_id="coordinator")
    response = client.get("/api/audit/stats?window_minutes=60", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["window_minutes"] == 60
    assert data["total_events"] >= 1
    assert "SUCCESS" in data["by_outcome"]
