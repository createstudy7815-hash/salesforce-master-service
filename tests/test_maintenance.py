from datetime import timedelta
import pytest
from app.models.job import JobStatus, utc_now
from app.services.job_service import job_service
from tests.conftest import make_hmac_headers


def test_detect_crashed_jobs_endpoint(client, db_session):
    # Create an active job with stale heartbeat (>15 min ago)
    scan_id = "scan_crashed_test"
    job = job_service.create_job(scan_id=scan_id, organization_id="00DOrg", db=db_session)
    job.status = JobStatus.DOWNLOADING
    job.last_heartbeat = utc_now() - timedelta(minutes=25)
    db_session.commit()

    path = "/api/maintenance/detect-crashed"
    headers = make_hmac_headers("POST", path)
    response = client.post(f"{path}?timeout_minutes=15", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert scan_id in data["crashed_job_ids"]

    # Verify job is now FAILED
    updated_job = job_service.get_job(scan_id, db=db_session)
    assert updated_job.status == JobStatus.FAILED
    assert "crashed or timed out" in updated_job.error_message


def test_cleanup_old_scans_endpoint(client, db_session):
    # Create an old completed scan (>40 days ago)
    scan_id = "scan_old_test"
    job = job_service.create_job(scan_id=scan_id, organization_id="00DOrg", db=db_session)
    job.created_at = utc_now() - timedelta(days=45)
    job.status = JobStatus.COMPLETED
    db_session.commit()

    path = "/api/maintenance/cleanup"
    headers = make_hmac_headers("POST", path)
    response = client.post(f"{path}?days_old=30", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert scan_id in data["deleted_scan_ids"]

    # Verify job deleted from DB
    assert job_service.get_job(scan_id, db=db_session) is None


def test_maintenance_requires_hmac(client):
    response = client.post("/api/maintenance/detect-crashed")
    assert response.status_code == 401
