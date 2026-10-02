# Salesforce Master Service

A standalone data extraction and normalization pipeline microservice for Salesforce.

This service pulls data out of Salesforce on demand using the Salesforce Bulk API 2.0, transforms and normalizes records into clean tabular formats (Parquet/JSON), and uploads the results to MinIO object storage.

---

## Current Status: Milestone Week 1 Complete ✅

- [x] **Project Scaffolding**: FastAPI architecture, configuration (`pydantic-settings`), Dockerfile, and `docker-compose.yml` (PostgreSQL 15 + MinIO).
- [x] **Database Models & Schemas**: SQLAlchemy models for `Job` (with full pipeline state machine), `AuditLog`, and `FailedExternalCall` (DLQ).
- [x] **Salesforce Authentication Client (`SalesforceAuthClient`)**:
  - OAuth 2.0 Username-Password flow
  - OAuth 2.0 JWT Bearer flow (RFC 7523)
  - In-memory token caching with near-expiry buffer (zero redundant external calls)
  - Credential validation without persisting secrets
- [x] **Core API Endpoints**:
  - `POST /api/validate-credentials` (Salesforce token grant & identity verification)
  - `GET /api/key/verify` (HMAC identity & role verification)
  - `GET /api/health` & `GET /health` (DB & MinIO readiness probe)
  - `GET /api/stats` (job statistics counter)
- [x] **CLI Credential Verification Script**: `scripts/test_login.py`
- [x] **Resilience & Security**: Bounded retry executor with exponential backoff & jitter; HMAC-SHA256 signature verification.
- [x] **Automated Test Suite**: 9 unit and integration tests passing (`100%` pass rate).

---

## Project Structure

```
salesforce-master-service/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── credentials.py   # POST /api/validate-credentials
│   │       │   ├── health.py        # GET /api/health, GET /api/stats
│   │       │   └── key.py           # GET /api/key/verify
│   │       └── router.py
│   ├── core/
│   │   ├── config.py                # Pydantic BaseSettings
│   │   ├── database.py              # SQLAlchemy engine & session dependency
│   │   ├── exceptions.py            # Domain exceptions
│   │   └── security.py              # HMAC signature authentication
│   ├── models/
│   │   ├── audit.py                 # AuditLog table
│   │   ├── dlq.py                   # FailedExternalCall table
│   │   └── job.py                   # Job table with full state machine
│   ├── schemas/
│   │   ├── auth.py                  # Credentials & token response schemas
│   │   └── common.py                # Health & stats schemas
│   ├── services/
│   │   ├── retry.py                 # Exponential backoff retry executor
│   │   └── sf_auth.py               # SalesforceAuthClient
│   └── main.py                      # FastAPI entrypoint
├── scripts/
│   └── test_login.py                # CLI script to test Salesforce credentials
├── tests/
│   ├── conftest.py                  # Pytest fixtures and in-memory test DB
│   ├── test_credentials_endpoint.py
│   ├── test_health.py
│   └── test_sf_auth.py
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
