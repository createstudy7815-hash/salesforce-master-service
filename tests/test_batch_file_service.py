import os
import pytest
from app.services.batch_file_service import BatchFileService


@pytest.fixture
def temp_file_service(tmp_path):
    return BatchFileService(base_dir=str(tmp_path))


def test_save_and_read_csv(temp_file_service):
    csv_data = "Id,Name,Industry\n001,Acme Corp,Manufacturing\n002,Global Tech,Technology\n003,BioPharm,Healthcare\n"
    scan_id = "test_scan_123"

    saved_path = temp_file_service.save_results_to_disk(scan_id, "Account", csv_data)
    assert os.path.exists(saved_path)

    # Read all records
    records, total = temp_file_service.read_csv_file(saved_path)
    assert total == 3
    assert len(records) == 3
    assert records[0]["Name"] == "Acme Corp"
    assert records[1]["Industry"] == "Technology"

    # Read with pagination
    page1, _ = temp_file_service.read_csv_file(saved_path, page=1, page_size=2)
    assert len(page1) == 2
    assert page1[0]["Id"] == "001"
    assert page1[1]["Id"] == "002"

    page2, _ = temp_file_service.read_csv_file(saved_path, page=2, page_size=2)
    assert len(page2) == 1
    assert page2[0]["Id"] == "003"


def test_get_file_info(temp_file_service):
    scan_id = "test_scan_info"
    acc_data = "Id,Name\n001,Alpha\n002,Beta\n"
    con_data = "Id,Email\n003,test@example.com\n"

    temp_file_service.save_results_to_disk(scan_id, "Account", acc_data)
    temp_file_service.save_results_to_disk(scan_id, "Contact", con_data)

    info = temp_file_service.get_file_info(scan_id)
    assert len(info["file_paths"]) == 2
    assert info["record_counts"]["Account"] == 2
    assert info["record_counts"]["Contact"] == 1
    assert info["file_sizes"]["Account"] == len(acc_data)
    assert info["file_sizes"]["Contact"] == len(con_data)


def test_infer_schema(temp_file_service):
    scan_id = "test_scan_schema"
    csv_data = "Id,Age,Salary,IsActive,Name\n1,30,125000.50,true,Alice\n2,45,95000.00,false,Bob\n"
    saved_path = temp_file_service.save_results_to_disk(scan_id, "Employee", csv_data)

    schema = temp_file_service.infer_schema(saved_path)
    assert schema["Id"] == "integer"
    assert schema["Age"] == "integer"
    assert schema["Salary"] == "float"
    assert schema["IsActive"] == "boolean"
    assert schema["Name"] == "string"


def test_cleanup_extracted_files(temp_file_service):
    scan_id = "test_scan_cleanup"
    temp_file_service.save_results_to_disk(scan_id, "Account", "Id,Name\n001,Test\n")
    assert os.path.exists(os.path.join(temp_file_service.base_dir, scan_id))

    cleaned = temp_file_service.cleanup_extracted_files(scan_id)
    assert cleaned is True
    assert not os.path.exists(os.path.join(temp_file_service.base_dir, scan_id))
