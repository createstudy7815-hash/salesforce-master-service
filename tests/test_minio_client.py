import os
import pytest
from unittest.mock import MagicMock, patch
from minio.error import S3Error
from app.services.minio_client import MinIOClient
from app.models.dlq import FailedExternalCall


def test_minio_client_initialization():
    client = MinIOClient(
        endpoint="localhost:9000",
        access_key="test_user",
        secret_key="test_secret",
        bucket_name="custom-bucket",
        secure=False
    )
    assert client.endpoint == "localhost:9000"
    assert client.access_key == "test_user"
    assert client.secret_key == "test_secret"
    assert client.bucket_name == "custom-bucket"
    assert client.secure is False
    assert client.client is not None


def test_minio_check_connection():
    client = MinIOClient()
    # Mock socket connection success
    with patch("socket.create_connection") as mock_conn:
        mock_sock = MagicMock()
        mock_conn.return_value = mock_sock
        assert client.check_connection() is True
        mock_sock.close.assert_called_once()

    # Mock socket connection failure
    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        assert client.check_connection() is False


def test_minio_ensure_bucket_exists():
    client = MinIOClient()
    client.client = MagicMock()

    # Case 1: Bucket already exists
    client.client.bucket_exists.return_value = True
    assert client.ensure_bucket_exists("my-bucket") is True
    client.client.bucket_exists.assert_called_with("my-bucket")
    client.client.make_bucket.assert_not_called()

    # Case 2: Bucket does not exist -> creates it
    client.client.bucket_exists.return_value = False
    assert client.ensure_bucket_exists("new-bucket") is True
    client.client.make_bucket.assert_called_with("new-bucket")


def test_minio_ensure_bucket_failure_dlq(db_session):
    client = MinIOClient()
    client.client = MagicMock()
    client.client.bucket_exists.side_effect = Exception("S3 access denied")

    result = client.ensure_bucket_exists("error-bucket", db=db_session)
    assert result is False

    dlq_entry = db_session.query(FailedExternalCall).filter(
        FailedExternalCall.target_service == "MinIO",
        FailedExternalCall.operation == "ensure_bucket_exists"
    ).first()
    assert dlq_entry is not None
    assert "access denied" in dlq_entry.last_error.lower()


def test_minio_upload_file(tmp_path):
    client = MinIOClient()
    client.client = MagicMock()
    client.client.bucket_exists.return_value = True

    test_file = tmp_path / "accounts.parquet"
    test_file.write_text("dummy parquet content")

    key = client.upload_file(str(test_file), "salesforce/accounts/accounts.parquet")
    assert key == "salesforce/accounts/accounts.parquet"
    client.client.fput_object.assert_called_once_with(
        bucket_name=client.bucket_name,
        object_name="salesforce/accounts/accounts.parquet",
        file_path=str(test_file)
    )


def test_minio_upload_file_exhaustion_writes_to_dlq(tmp_path, db_session):
    client = MinIOClient()
    client.client = MagicMock()
    client.client.bucket_exists.return_value = True
    client.client.fput_object.side_effect = Exception("MinIO network timeout")

    test_file = tmp_path / "contacts.parquet"
    test_file.write_text("dummy contact data")

    with pytest.raises(Exception):
        client.upload_file(str(test_file), "salesforce/contacts/contacts.parquet", db=db_session)

    dlq_entry = db_session.query(FailedExternalCall).filter(
        FailedExternalCall.target_service == "MinIO",
        FailedExternalCall.operation == "upload_file"
    ).first()
    assert dlq_entry is not None
    assert "network timeout" in dlq_entry.last_error


def test_minio_upload_directory(tmp_path):
    client = MinIOClient()
    client.client = MagicMock()
    client.client.bucket_exists.return_value = True

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "accounts.parquet").write_text("accounts")
    sub_dir = data_dir / "nested"
    sub_dir.mkdir()
    (sub_dir / "contacts.parquet").write_text("contacts")

    keys = client.upload_directory(str(data_dir), "exports/test")
    assert len(keys) == 2
    assert "exports/test/accounts.parquet" in keys
    assert "exports/test/nested/contacts.parquet" in keys


def test_minio_upload_normalized_data_partitioned_paths(tmp_path):
    client = MinIOClient()
    client.client = MagicMock()
    client.client.bucket_exists.return_value = True

    acc_file = tmp_path / "accounts.parquet"
    acc_file.write_text("accounts")
    opp_file = tmp_path / "opportunities.parquet"
    opp_file.write_text("opps")

    tables = {
        "accounts": {"file_path": str(acc_file)},
        "opportunities": {"file_path": str(opp_file)}
    }

    keys = client.upload_normalized_data(
        scan_id="scan_123",
        organization_id="00D5g00000abc123",
        processing_date="2026-10-29",
        tables=tables
    )

    assert len(keys) == 2
    expected_acc = "salesforce/accounts/glynac_organization_id=00D5g00000abc123/processing_date=2026-10-29/accounts.parquet"
    expected_opp = "salesforce/opportunities/glynac_organization_id=00D5g00000abc123/processing_date=2026-10-29/opportunities.parquet"

    assert expected_acc in keys
    assert expected_opp in keys


def test_minio_download_file(tmp_path):
    client = MinIOClient()
    client.client = MagicMock()

    dest = tmp_path / "downloaded.parquet"
    key = "salesforce/accounts/accounts.parquet"

    path = client.download_file(key, str(dest))
    assert path == str(dest)
    client.client.fget_object.assert_called_once_with(
        bucket_name=client.bucket_name,
        object_name=key,
        file_path=str(dest)
    )


def test_minio_list_and_delete_objects():
    client = MinIOClient()
    client.client = MagicMock()

    obj1 = MagicMock()
    obj1.object_name = "prefix/file1.parquet"
    obj2 = MagicMock()
    obj2.object_name = "prefix/file2.parquet"
    client.client.list_objects.return_value = [obj1, obj2]

    keys = client.list_objects("prefix")
    assert keys == ["prefix/file1.parquet", "prefix/file2.parquet"]

    # Delete
    success = client.delete_object("prefix/file1.parquet")
    assert success is True
    client.client.remove_object.assert_called_once_with(client.bucket_name, "prefix/file1.parquet")
