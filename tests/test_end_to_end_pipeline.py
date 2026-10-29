import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.job import Job, JobStatus
from app.models.dlq import FailedExternalCall
from app.schemas.auth import SalesforceCredentials
from app.services.job_service import job_service
from app.services.extraction_service import extraction_service
from app.services.batch_file_service import batch_file_service
from tests.conftest import make_hmac_headers


@pytest.mark.asyncio
async def test_end_to_end_pipeline_full_lifecycle(client, db_session, tmp_path):
    """
    Test full end-to-end automated pipeline:
    Scan Start -> Bulk Query -> Poll -> Download -> Extract -> Normalize (Parquet) -> MinIO Upload -> COMPLETED
    """
    scan_id = "scan_e2e_001"
    org_id = "00D_Org_Test_Full"

    job = job_service.create_job(scan_id=scan_id, organization_id=org_id, db=db_session)
    assert job.status == JobStatus.PENDING

    # Setup extracted dummy CSV for accounts
    extracted_dir = batch_file_service.get_extracted_dir(scan_id)
    os.makedirs(extracted_dir, exist_ok=True)
    sample_csv = os.path.join(extracted_dir, "Account.csv")
    with open(sample_csv, "w", encoding="utf-8") as f:
        f.write("Id,Name,BillingCity,BillingCountry,AnnualRevenue\n")
        f.write("001XX001,Acme Corp,San Francisco,USA,5000000\n")
        f.write("001XX002,Global Tech,New York,USA,12000000\n")

    creds = SalesforceCredentials(
        login_url="https://login.salesforce.com",
        client_id="cid",
        username="user@example.com",
        password="secretpassword"
    )

    mock_uploaded_keys = [
        f"salesforce/accounts/glynac_organization_id={org_id}/processing_date=2026-10-29/accounts.parquet",
        f"salesforce/account_addresses/glynac_organization_id={org_id}/processing_date=2026-10-29/account_addresses.parquet"
    ]

    with patch("app.services.batch_polling_service.batch_polling_service.submit_batch_jobs", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.batch_polling_service.batch_polling_service.poll_until_ready", new_callable=AsyncMock) as mock_poll, \
         patch("app.services.batch_polling_service.batch_polling_service.download_results", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.minio_client.minio_client.upload_normalized_data", return_value=mock_uploaded_keys) as mock_minio_upload:

        mock_poll.return_value = {"status": "JobComplete"}

        await extraction_service._execute_batch_workflow(
            scan_id=scan_id,
            creds=creds,
            objects=["Account"],
            auto_normalize=True,
            upload_to_minio=True,
            output_format="parquet",
            processing_date="2026-10-29",
            db=db_session
        )

        mock_submit.assert_called_once()
        mock_poll.assert_called_once()
        mock_dl.assert_called_once()
        mock_minio_upload.assert_called_once()

    updated_job = job_service.get_job(scan_id, db=db_session)
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.extracted_at is not None
    assert updated_job.normalized_at is not None
    assert updated_job.minio_uploaded_at is not None
    assert updated_job.minio_object_keys == mock_uploaded_keys
    assert updated_job.entity_record_counts.get("Account") == 2

    # Check pipeline progress response
    progress = job_service.get_pipeline_progress(updated_job)
    assert progress["current_status"] == "COMPLETED"
    assert progress["stages"]["extracted"] is True
    assert progress["stages"]["normalized"] is True
    assert progress["stages"]["minio_uploaded"] is True
    assert progress["stages"]["completed"] is True


@pytest.mark.asyncio
async def test_resume_scan_from_extracted_stage(db_session):
    """
    Test resumption when a scan failed during normalization.
    """
    scan_id = "scan_resume_norm"
    org_id = "00D_Org_Resume"

    job = job_service.create_job(scan_id=scan_id, organization_id=org_id, db=db_session)
    # Mark as extracted
    job_service.update_job_status(scan_id, JobStatus.EXTRACTED, db=db_session)
    job_service.update_extraction_info(scan_id, {"Account": 5}, db=db_session)
    # Simulate a subsequent failure
    job_service.fail_job(scan_id, "Memory error during normalization", db=db_session)

    extracted_dir = batch_file_service.get_extracted_dir(scan_id)
    os.makedirs(extracted_dir, exist_ok=True)
    sample_csv = os.path.join(extracted_dir, "Account.csv")
    with open(sample_csv, "w", encoding="utf-8") as f:
        f.write("Id,Name\n0011,Test Inc\n")

    creds = SalesforceCredentials(
        login_url="https://login.salesforce.com",
        client_id="cid",
        username="u@test.com",
        password="pwd"
    )

    with patch("app.services.minio_client.minio_client.upload_normalized_data", return_value=["key1", "key2"]):
        await extraction_service._execute_resume_workflow(
            scan_id=scan_id,
            creds=creds,
            db=db_session
        )

    resumed_job = job_service.get_job(scan_id, db=db_session)
    assert resumed_job.status in (JobStatus.NORMALIZED, JobStatus.COMPLETED)
    assert resumed_job.normalized_at is not None


@pytest.mark.asyncio
async def test_resume_scan_from_normalized_stage(db_session):
    """
    Test resumption when a scan completed normalization but failed during MinIO upload.
    """
    scan_id = "scan_resume_minio"
    org_id = "00D_Org_MinIO_Resume"

    job = job_service.create_job(scan_id=scan_id, organization_id=org_id, db=db_session)
    job_service.complete_normalization(
        scan_id=scan_id,
        normalization_stats={"table_stats": {"accounts": {"file_path": "/dummy/accounts.parquet"}}},
        db=db_session
    )
    job_service.fail_job(scan_id, "S3 connection timeout", db=db_session)

    creds = SalesforceCredentials(
        login_url="https://login.salesforce.com",
        client_id="cid",
        username="u@test.com",
        password="pwd"
    )

    mock_keys = ["salesforce/accounts/glynac_organization_id=00D_Org_MinIO_Resume/accounts.parquet"]
    with patch("app.services.minio_client.minio_client.upload_normalized_data", return_value=mock_keys):
        await extraction_service._execute_resume_workflow(
            scan_id=scan_id,
            creds=creds,
            db=db_session
        )

    resumed_job = job_service.get_job(scan_id, db=db_session)
    assert resumed_job.status == JobStatus.COMPLETED
    assert resumed_job.minio_uploaded_at is not None
    assert resumed_job.minio_object_keys == mock_keys


@pytest.mark.asyncio
async def test_pipeline_minio_upload_failure_handling(db_session):
    """
    Test that if MinIO upload throws an unrecoverable error during the pipeline,
    the job is marked as FAILED with a detailed error.
    """
    scan_id = "scan_minio_fail"
    org_id = "00D_Org_Fail"

    job = job_service.create_job(scan_id=scan_id, organization_id=org_id, db=db_session)

    extracted_dir = batch_file_service.get_extracted_dir(scan_id)
    os.makedirs(extracted_dir, exist_ok=True)
    sample_csv = os.path.join(extracted_dir, "Account.csv")
    with open(sample_csv, "w", encoding="utf-8") as f:
        f.write("Id,Name\n0011,Test Inc\n")

    creds = SalesforceCredentials(
        login_url="https://login.salesforce.com",
        client_id="cid",
        username="u@test.com",
        password="pwd"
    )

    with patch("app.services.batch_polling_service.batch_polling_service.submit_batch_jobs", new_callable=AsyncMock), \
         patch("app.services.batch_polling_service.batch_polling_service.poll_until_ready", new_callable=AsyncMock, return_value={"status": "JobComplete"}), \
         patch("app.services.batch_polling_service.batch_polling_service.download_results", new_callable=AsyncMock), \
         patch("app.services.minio_client.minio_client.upload_normalized_data", side_effect=RuntimeError("MinIO storage unavailable")):

        await extraction_service._execute_batch_workflow(
            scan_id=scan_id,
            creds=creds,
            objects=["Account"],
            auto_normalize=True,
            upload_to_minio=True,
            db=db_session
        )

    failed_job = job_service.get_job(scan_id, db=db_session)
    assert failed_job.status == JobStatus.FAILED
    assert "MinIO storage unavailable" in failed_job.error_message


def test_health_check_healthy_and_degraded(client):
    """
    Verify GET /api/health returns ok when both DB and MinIO are healthy,
    and returns degraded when MinIO is down.
    """
    # 1. Healthy
    with patch("app.services.minio_client.minio_client.check_connection", return_value=True):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database_connected"] is True
        assert data["minio_connected"] is True

    # 2. Degraded
    with patch("app.services.minio_client.minio_client.check_connection", return_value=False):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "degraded"
        assert data["database_connected"] is True
        assert data["minio_connected"] is False

