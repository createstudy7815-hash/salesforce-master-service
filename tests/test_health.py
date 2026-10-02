def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "salesforce-master-service"
    assert data["status"] == "online"


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["database_connected"] is True
    assert data["version"] == "0.1.0"


def test_service_stats(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 0
    assert data["active_jobs"] == 0
