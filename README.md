# Salesforce Master Service

A standalone data extraction and normalization pipeline microservice for Salesforce.

This service pulls data out of Salesforce on demand using the Salesforce Bulk API 2.0, transforms and normalizes records into clean tabular formats (Parquet/JSON), and uploads the results to MinIO object storage.

---

## Current Status: Milestone Week 1 Complete ✅ (Week 2 Next ⏳)

### ✅ Completed in Milestone Week 1:
- [x] **Project Scaffolding**: FastAPI architecture, configuration (`pydantic-settings`), Dockerfile, and `docker-compose.yml` (PostgreSQL 15 + MinIO).
- [x] **Database Models & Schemas**:
  - `Job` tracking table with 15-state lifecycle and heartbeat tracking.
  - `AuditLog` table for security and operation auditing.
  - `FailedExternalCall` table for Dead-Letter Queue (DLQ).
- [x] **Salesforce Authentication Client (`SalesforceAuthClient`)**:
  - OAuth 2.0 Username-Password flow
  - OAuth 2.0 JWT Bearer flow (RFC 7523)
  - In-memory token caching with near-expiry buffer
  - Credential validation without persisting secrets
- [x] **HMAC-SHA256 Security & Authentication**:
  - Dual-key scheme: Coordinator (full access) & Engineer (read-only)
  - Canonical request signing (`METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(BODY)`)
  - Nonce replay attack protection and timestamp freshness validation (300s window)
  - Role enforcement (Engineer role restricted to read-only methods)
- [x] **Resilience & Dead-Letter Queue (DLQ)**:
  - Bounded exponential retry engine with backoff and jitter (`retry_call`)
  - Transient error classification (`is_retryable`) for network timeouts, 408, 429, 500, 502, 503, 504
  - DLQ persistence with recursive sensitive credential scrubbing (`scrub_payload`)
- [x] **Audit Logging Service (`AuditService`)**:
  - Fire-and-forget, non-blocking audit logging
  - Endpoints to query audit logs with pagination and filters
  - Rolling-window audit statistics aggregations
- [x] **Core API Endpoints**:
  - `POST /api/validate-credentials` (HMAC-protected credential verification)
  - `GET /api/key/verify` (HMAC caller identity & role verification)
  - `GET /api/audit/logs` & `GET /api/audit/stats` (Audit inspection)
  - `GET /api/health` & `GET /health` (DB & MinIO readiness probe)
  - `GET /api/stats` (job statistics counter)
  - `GET /` (service status)
- [x] **CLI Credential Verification Script**: `scripts/test_login.py`
- [x] **Automated Test Suite**: 24 unit and integration tests passing (`100%` pass rate).

---

## Project Structure

```
salesforce-master-service/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── audit.py         # GET /api/audit/logs, GET /api/audit/stats
│   │       │   ├── credentials.py   # POST /api/validate-credentials
│   │       │   ├── health.py        # GET /api/health, GET /api/stats
│   │       │   └── key.py           # GET /api/key/verify
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
│   │   └── common.py                # Health & stats schemas
│   ├── services/
│   │   ├── audit.py                 # AuditService logging & stats aggregation
│   │   └── sf_auth.py               # SalesforceAuthClient with retry & caching
│   └── main.py                      # FastAPI entrypoint
├── scripts/
│   └── test_login.py                # CLI script to test Salesforce credentials
├── tests/
│   ├── conftest.py                  # Pytest fixtures, test DB, and HMAC helper
│   ├── test_audit.py                # Audit log & stats tests
│   ├── test_credentials_endpoint.py
│   ├── test_health.py
│   ├── test_hmac_auth.py            # HMAC security & authorization tests
│   ├── test_resilience.py           # Retry & DLQ resilience tests
│   └── test_sf_auth.py              # Salesforce auth client tests
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
