import os
import json
import pytest
from app.models.job import Job, JobStatus
from app.services.job_service import job_service
from app.services.batch_file_service import batch_file_service
from tests.conftest import make_hmac_headers


@pytest.fixture
def sample_extracted_scan(db_session):
    scan_id = "scan_test_norm_001"
    job = job_service.create_job(
        scan_id=scan_id,
        organization_id="00Dxx0000001Org",
        db=db_session
    )

    # Create dummy extracted CSV files
    account_csv = (
        "Id,Name,BillingCity,BillingCountry,AnnualRevenue\n"
        "001A,Acme Corp,San Francisco,USA,1000000\n"
        "001B,Globex Inc,New York,USA,2500000\n"
    )
    contact_csv = (
        "Id,AccountId,FirstName,LastName,Email\n"
        "003A,001A,Alice,Smith,alice@acme.com\n"
    )

    batch_file_service.save_results_to_disk(scan_id, "Account", account_csv)
    batch_file_service.save_results_to_disk(scan_id, "Contact", contact_csv)

    yield scan_id

    # Teardown
    batch_file_service.cleanup_extracted_files(scan_id)


def test_supported_objects_endpoint(client):
    headers = make_hmac_headers("GET", "/api/normalization/supported-objects")
    response = client.get("/api/normalization/supported-objects", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "supported_objects" in data
    names = [obj["object_name"] for obj in data["supported_objects"]]
    assert "Account" in names
    assert "Contact" in names
    assert "Opportunity" in names


def test_normalize_scan_full(client, sample_extracted_scan, db_session):
    scan_id = sample_extracted_scan
    body = json.dumps({"format": "parquet", "save_to_disk": True}).encode("utf-8")
    headers = make_hmac_headers("POST", f"/api/normalization/{scan_id}/normalize", body=body)

    response = client.post(
        f"/api/normalization/{scan_id}/normalize",
        content=body,
        headers={**headers, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scan_id"] == scan_id
    assert data["format"] == "parquet"
    assert "accounts" in data["tables_generated"]
    assert "contacts" in data["tables_generated"]
    assert data["total_records"] >= 3

    # Verify Job status updated to NORMALIZED
    job = job_service.get_job(scan_id, db=db_session)
    assert job.status == JobStatus.NORMALIZED
    assert job.normalized_at is not None
    assert "accounts" in job.normalization_stats["tables_generated"]


def test_section_6_normalize_alias(client, sample_extracted_scan, db_session):
    scan_id = sample_extracted_scan
    body = json.dumps({"format": "json", "save_to_disk": True}).encode("utf-8")
    headers = make_hmac_headers("POST", f"/api/normalize/{scan_id}", body=body)

    response = client.post(
        f"/api/normalize/{scan_id}",
        content=body,
        headers={**headers, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "json"
    assert "accounts" in data["tables_generated"]


def test_normalize_single_object_endpoint(client, sample_extracted_scan):
    scan_id = sample_extracted_scan
    headers = make_hmac_headers("POST", f"/api/normalization/{scan_id}/normalize/Account")
    response = client.post(f"/api/normalization/{scan_id}/normalize/Account", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object_name"] == "Account"
    assert "accounts" in data["tables_generated"]
    assert data["table_stats"]["accounts"]["row_count"] == 2


def test_list_normalized_tables_endpoint(client, sample_extracted_scan):
    scan_id = sample_extracted_scan
    # First normalize so files exist
    body = json.dumps({"format": "parquet", "save_to_disk": True}).encode("utf-8")
    headers = make_hmac_headers("POST", f"/api/normalization/{scan_id}/normalize", body=body)
    client.post(f"/api/normalization/{scan_id}/normalize", content=body, headers={**headers, "Content-Type": "application/json"})

    # Now call list tables
    list_headers = make_hmac_headers("GET", f"/api/normalization/{scan_id}/tables")
    response = client.get(f"/api/normalization/{scan_id}/tables", headers=list_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["scan_id"] == scan_id
    assert data["total_tables"] >= 2
    table_names = [t["table_name"] for t in data["tables"]]
    assert "accounts" in table_names


def test_normalize_nonexistent_scan(client):
    body = json.dumps({}).encode("utf-8")
    headers = make_hmac_headers("POST", "/api/normalization/non_existent_scan/normalize", body=body)
    response = client.post("/api/normalization/non_existent_scan/normalize", content=body, headers={**headers, "Content-Type": "application/json"})
    assert response.status_code == 404


def test_normalize_requires_hmac(client, sample_extracted_scan):
    # Without HMAC headers, should be rejected with 401 Unauthorized
    response = client.post(f"/api/normalization/{sample_extracted_scan}/normalize")
    assert response.status_code == 401
