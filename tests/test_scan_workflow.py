import json
import pytest
from unittest.mock import AsyncMock, patch

from app.models.job import Job, JobStatus
from app.services.job_service import job_service
from tests.conftest import make_hmac_headers


def test_batch_info_endpoint(client):
    headers = make_hmac_headers("GET", "/api/batch/info", b"", client_id="coordinator")
    response = client.get("/api/batch/info", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "supported_objects" in data
    assert "Account" in data["supported_objects"]
    assert "query_defaults" in data


def test_scan_start_endpoint(client):
    payload = {
        "organization_id": "00DTestOrg123",
        "credentials": {
            "login_url": "https://login.salesforce.com",
            "client_id": "cid",
            "client_secret": "csec",
            "username": "user@test.com",
            "password": "pwd"
        },
        "objects": ["Account", "Contact"]
    }
    body = json.dumps(payload).encode("utf-8")
    headers = make_hmac_headers("POST", "/api/scan/start", body, client_id="coordinator")

    with patch("app.services.extraction_service.extraction_service._execute_batch_workflow", new_callable=AsyncMock):
        response = client.post(
            "/api/scan/start",
            content=body,
            headers={"Content-Type": "application/json", **headers}
        )
        assert response.status_code == 202
        data = response.json()
        assert data["organization_id"] == "00DTestOrg123"
        assert data["status"] == "PENDING"
        assert data["scan_id"].startswith("scan_")


def test_scan_status_and_lifecycle(client, db_session):
    # Create test job
    job = job_service.create_job(scan_id="scan_lifecycle_1", organization_id="00DOrg999", db=db_session)
    job_service.update_job_status(job.id, JobStatus.EXTRACTED, db=db_session)

    # 1. Status check
    headers = make_hmac_headers("GET", f"/api/scan/{job.id}/status", b"", client_id="coordinator")
    res = client.get(f"/api/scan/{job.id}/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["scan_id"] == job.id
    assert data["status"] == "EXTRACTED"
    assert "pipeline_progress" in data

    # 2. Cancel scan
    cancel_headers = make_hmac_headers("POST", f"/api/scan/{job.id}/cancel", b"", client_id="coordinator")
    res = client.post(f"/api/scan/{job.id}/cancel", headers=cancel_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"

    # 3. Resume scan
    resume_payload = {
        "login_url": "https://login.salesforce.com",
        "client_id": "cid",
        "username": "user@test.com",
        "password": "pwd"
    }
    resume_body = json.dumps(resume_payload).encode("utf-8")
    resume_headers = make_hmac_headers("POST", f"/api/scan/{job.id}/resume", resume_body, client_id="coordinator")

    with patch("app.services.extraction_service.extraction_service._execute_resume_workflow", new_callable=AsyncMock):
        res = client.post(
            f"/api/scan/{job.id}/resume",
            content=resume_body,
            headers={"Content-Type": "application/json", **resume_headers}
        )
        assert res.status_code == 200

    # 4. List scans
    list_headers = make_hmac_headers("GET", "/api/scan/list", b"", client_id="coordinator")
    res = client.get("/api/scan/list", headers=list_headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # 5. Scan statistics
    stats_headers = make_hmac_headers("GET", "/api/scan/statistics", b"", client_id="coordinator")
    res = client.get("/api/scan/statistics", headers=stats_headers)
    assert res.status_code == 200
    assert res.json()["total_scans"] >= 1

    # 6. Remove scan
    delete_headers = make_hmac_headers("DELETE", f"/api/scan/{job.id}/remove", b"", client_id="coordinator")
    res = client.delete(f"/api/scan/{job.id}/remove", headers=delete_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "DELETED"


@pytest.mark.asyncio
async def test_execute_batch_workflow_end_to_end(db_session):
    from app.services.extraction_service import extraction_service
    from app.schemas.auth import SalesforceCredentials

    scan_id = "scan_e2e_test"
    job_service.create_job(scan_id=scan_id, organization_id="00DOrgE2E", db=db_session)

    creds = SalesforceCredentials(
        login_url="https://test.salesforce.com",
        client_id="cid",
        username="u@test.com",
        password="pwd"
    )

    with patch("app.services.batch_polling_service.batch_polling_service.submit_batch_jobs", new_callable=AsyncMock) as mock_sub, \
         patch("app.services.batch_polling_service.batch_polling_service.poll_until_ready", new_callable=AsyncMock) as mock_poll, \
         patch("app.services.batch_polling_service.batch_polling_service.download_results", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.batch_file_service.batch_file_service.get_file_info") as mock_info:

        mock_sub.return_value = {"Account": "750001"}
        mock_poll.return_value = {"status": "JobComplete"}
        mock_dl.return_value = ["data/scans/scan_e2e_test/extracted/Account.csv"]
        mock_info.return_value = {
            "file_paths": ["data/scans/scan_e2e_test/extracted/Account.csv"],
            "file_sizes": {"Account": 256},
            "record_counts": {"Account": 5}
        }

        await extraction_service._execute_batch_workflow(
            scan_id=scan_id,
            creds=creds,
            objects=["Account"],
            db=db_session
        )

        job = job_service.get_job(scan_id, db=db_session)
        assert job.status == JobStatus.EXTRACTED
        assert job.entity_record_counts == {"Account": 5}
