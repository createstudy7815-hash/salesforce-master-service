# Salesforce Master Service

A standalone data extraction and normalization pipeline service for Salesforce.

This service pulls data out of Salesforce on demand using the Salesforce Bulk API 2.0, transforms and normalizes records into clean tabular formats (Parquet/JSON), and uploads the results to MinIO object storage.

## Features

- **Bulk API 2.0 Integration**: Asynchronously exports Salesforce objects (Accounts, Contacts, Opportunities, Leads, Cases, Tasks/Events, Campaigns, Users).
- **Relational Normalization**: Flattens nested Salesforce records into clean, queryable tables.
- **Resilient Pipeline**: State tracking in PostgreSQL, heartbeat-based crash detection, and resumable scans.
- **Object Storage**: Publishes partitioned Parquet datasets directly to MinIO.
- **Security**: HMAC-SHA256 signature verification for Coordinator requests.
- **Dead-Letter Queue (DLQ)**: Automatic retries with exponential backoff and failed call persistence.

## Architecture & Design

For complete architectural details, state machine transitions, and API specifications, see [DESIGN.md](DESIGN.md).

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- MinIO

### Quickstart (Local Development)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/salesforce-master-service.git
   cd salesforce-master-service
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your Salesforce, PostgreSQL, and MinIO credentials.

4. **Run Services with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

5. **Run Tests:**
   ```bash
   pytest
   ```
