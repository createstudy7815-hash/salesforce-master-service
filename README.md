# Salesforce Master Service

A standalone data extraction and normalization pipeline microservice for Salesforce.

This service pulls data out of Salesforce on demand using the Salesforce Bulk API 2.0, transforms and normalizes records into clean tabular formats (Parquet/JSON), and uploads the results to MinIO object storage.

---

## Current Status: Milestone Week 1 & 2 Complete ✅ (Week 3 Next ⏳)

### ✅ Completed in Milestone Week 1 (Setup, Auth & Security):
- [x] **Project Scaffolding**: FastAPI architecture, configuration (`pydantic-settings`), Dockerfile, and `docker-compose.yml` (PostgreSQL 15 + MinIO).
- [x] **Database Models & Schemas**: `Job` table with 15-state lifecycle, `AuditLog` table, `FailedExternalCall` DLQ table.
- [x] **Salesforce Authentication Client (`SalesforceAuthClient`)**: Username-Password & JWT Bearer flows, in-memory caching, validation.
- [x] **HMAC-SHA256 Security & Authentication**: Dual-key scheme (Coordinator & Engineer), replay protection, timestamp freshness check.
- [x] **Resilience & DLQ**: Bounded exponential backoff with jitter (`retry_call`), DLQ persistence with credential scrubbing (`scrub_payload`).
- [x] **Audit Logging Service (`AuditService`)**: Non-blocking audit logger, audit query API (`/api/audit/logs`), rolling statistics (`/api/audit/stats`).

### ✅ Completed in Milestone Week 2 (Bulk API 2.0 & Data Extraction):
- [x] **Salesforce Bulk API 2.0 Client (`SalesforceBatchAPIClient`)**:
  - Submits SOQL query jobs per object (`POST /services/data/vXX.X/jobs/query`).
  - Polls job state (`UploadComplete`, `InProgress`, `JobComplete`, `Failed`, `Aborted`).
  - Streams and pages CSV result data (`GET /services/data/vXX.X/jobs/query/{id}/results`).
  - Remote job cancellation/abortion (`PATCH /services/data/vXX.X/jobs/query/{id}`).
- [x] **Batch Polling & Coordination Service (`BatchPollingService`)**:
  - Multi-object batch job submission and state aggregation.
  - Heartbeat-driven polling loop with configurable intervals and timeouts.
  - Automatic CSV results downloader with locator-based paging.
- [x] **Local File Management (`BatchFileService`)**:
  - Saves raw CSV extractions to `data/scans/{scan_id}/extracted/{object_name}.csv`.
  - Paginated CSV reader and schema type inferrer.
  - Disk footprint and record count analyzer; cleanup utilities.
- [x] **Job State Management (`JobService`)**:
  - Stage tracking, per-object batch job mapping, heartbeat refresher.
  - Crash detection mechanism (`detect_crashed_jobs`) for stale heartbeats.
  - Scan removal and paginated listing.
- [x] **Extraction Orchestrator (`ExtractionService`)**:
  - Non-blocking scan initiation (returns 202 Accepted immediately).
  - Background workflow execution (`Submit` ➔ `Poll` ➔ `Download` ➔ `Extract`).
  - Crash recovery / resume workflow from last completed stage.
  - Local and remote cancellation.
- [x] **Scan & Batch API Routers**:
  - `POST /api/scan/start`
  - `GET /api/scan/{id}/status`
  - `POST /api/scan/{id}/cancel`
  - `POST /api/scan/{id}/resume`
  - `GET /api/scan/list`
  - `GET /api/scan/statistics`
  - `DELETE /api/scan/{id}/remove`
  - `GET /api/batch/info`
- [x] **Automated Test Suite**: **36 unit and integration tests passing (`100%` pass rate)**.

---

## Project Structure

```
salesforce-master-service/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── audit.py         # GET /api/audit/logs, GET /api/audit/stats
│   │       │   ├── batch.py         # GET /api/batch/info
│   │       │   ├── credentials.py   # POST /api/validate-credentials
│   │       │   ├── health.py        # GET /api/health, GET /api/stats
│   │       │   ├── key.py           # GET /api/key/verify
│   │       │   └── scan.py          # /api/scan/* lifecycle endpoints
│   │       └── router.py
│   ├── core/
│   │   ├── config.py                # Pydantic BaseSettings & environment configs
│   │   ├── database.py              # SQLAlchemy engine & session dependency
│   │   ├── dlq.py                   # Dead-letter queue with payload scrubbing
│   │   ├── exceptions.py            # Domain exceptions
│   │   ├── hmac_auth.py             # HMAC-SHA256 auth middleware & replay guard
│   │   └── retry.py                 # Exponential backoff retry engine
│   ├── models/
│   │   ├── audit.py                 # AuditLog database model
│   │   ├── dlq.py                   # FailedExternalCall DLQ model
│   │   └── job.py                   # Job table with 15-state lifecycle
│   ├── schemas/
│   │   ├── auth.py                  # Credentials & token response schemas
│   │   ├── batch.py                 # Bulk API batch metadata schema
│   │   ├── common.py                # Health & stats schemas
│   │   └── scan.py                  # Scan request/response schemas
│   ├── services/
│   │   ├── audit.py                 # AuditService logging & stats aggregation
│   │   ├── batch_file_service.py    # Local CSV dataset storage manager
│   │   ├── batch_polling_service.py # Bulk API polling & download manager
│   │   ├── extraction_service.py    # Top-level scan orchestrator
│   │   ├── job_service.py           # Job tracking & state machine service
│   │   ├── sf_auth.py               # SalesforceAuthClient with retry & caching
│   │   └── sf_batch_client.py       # Salesforce Bulk API 2.0 query client
│   └── main.py                      # FastAPI entrypoint
├── scripts/
│   └── test_login.py                # CLI script to test Salesforce credentials
├── tests/
│   ├── conftest.py                  # Pytest fixtures, test DB, and HMAC helper
│   ├── test_audit.py                # Audit log & stats tests
│   ├── test_batch_file_service.py   # CSV file storage & schema tests
│   ├── test_credentials_endpoint.py
│   ├── test_health.py
│   ├── test_hmac_auth.py            # HMAC security & authorization tests
│   ├── test_resilience.py           # Retry & DLQ resilience tests
│   ├── test_scan_workflow.py        # Scan lifecycle & pipeline workflow tests
│   ├── test_sf_auth.py              # Salesforce auth client tests
│   └── test_sf_batch_client.py      # Bulk API 2.0 client tests
├── docker-compose.yml               # PostgreSQL, MinIO, FastAPI app
├── Dockerfile
├── requirements.txt
├── .env.example
├── pytest.ini
└── DESIGN.md                        # Master specification document
```

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Virtual environment tool (`venv`)
- (Optional) Docker & Docker Compose for containerized PostgreSQL & MinIO

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
pytest -v
```

### 4. Test Salesforce Login (CLI)
You can test your Salesforce account credentials directly using the CLI utility:

```bash
python scripts/test_login.py \
    --username your_user@example.com \
    --password your_password \
    --security-token your_token \
    --client-id your_connected_app_client_id \
    --client-secret your_connected_app_client_secret
```

Or for JWT Bearer Flow:
```bash
python scripts/test_login.py \
    --username your_user@example.com \
    --client-id your_connected_app_client_id \
    --jwt-key-path path/to/server.key
```

### 5. Start the API Server
```bash
uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000/docs](http://localhost:8000/docs)** to view the interactive Swagger API documentation.
