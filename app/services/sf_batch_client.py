import logging
from typing import Dict, Any, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.retry import retry_call
from app.schemas.auth import SalesforceCredentials
from app.services.sf_auth import sf_auth_client

logger = logging.getLogger(__name__)

DEFAULT_SOQL_QUERIES: Dict[str, str] = {
    "Account": "SELECT Id, Name, Type, Phone, Industry, AnnualRevenue, BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry, CreatedDate, SystemModstamp FROM Account",
    "Contact": "SELECT Id, AccountId, FirstName, LastName, Email, Phone, Title, Department, CreatedDate, SystemModstamp FROM Contact",
    "Opportunity": "SELECT Id, AccountId, Name, StageName, Amount, CloseDate, Probability, Type, LeadSource, IsClosed, IsWon, CreatedDate, SystemModstamp FROM Opportunity",
    "Lead": "SELECT Id, FirstName, LastName, Company, Email, Phone, Status, LeadSource, Industry, AnnualRevenue, CreatedDate, SystemModstamp FROM Lead",
    "Case": "SELECT Id, AccountId, ContactId, CaseNumber, Status, Priority, Subject, Description, Origin, CreatedDate, ClosedDate, SystemModstamp FROM Case",
    "Task": "SELECT Id, WhoId, WhatId, Subject, Status, Priority, ActivityDate, Description, CreatedDate, SystemModstamp FROM Task",
    "Event": "SELECT Id, WhoId, WhatId, Subject, StartDateTime, EndDateTime, Description, CreatedDate, SystemModstamp FROM Event",
    "Campaign": "SELECT Id, Name, Status, IsActive, Type, StartDate, EndDate, ExpectedRevenue, BudgetedCost, ActualCost, CreatedDate, SystemModstamp FROM Campaign",
    "User": "SELECT Id, Username, LastName, FirstName, Name, Email, IsActive, UserType, CreatedDate, SystemModstamp FROM User"
}


class SalesforceBatchAPIClient:
    """
    Salesforce Bulk API 2.0 Query Client:
    - Create SOQL query jobs per object
    - Poll job execution status
    - Stream / retrieve CSV dataset results
    - Abort / cancel in-flight jobs
    """
    def __init__(self, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds
        self.api_version = settings.SF_API_VERSION

    async def _get_auth_headers(self, creds: SalesforceCredentials) -> Tuple[Dict[str, str], str]:
        """Obtain authorization headers and instance_url from token."""
        token_resp = await sf_auth_client.get_access_token(creds)
        headers = {
            "Authorization": f"Bearer {token_resp.access_token}",
            "Content-Type": "application/json"
        }
        return headers, token_resp.instance_url.rstrip("/")

    async def create_query_job(
        self,
        object_name: str,
        creds: SalesforceCredentials,
        soql: Optional[str] = None,
        operation: str = "query"
    ) -> Dict[str, Any]:
        """
        Create a Bulk API 2.0 query job for an object.
        POST /services/data/vXX.X/jobs/query
        """
        headers, base_url = await self._get_auth_headers(creds)
        query = soql or DEFAULT_SOQL_QUERIES.get(object_name, f"SELECT Id, CreatedDate, SystemModstamp FROM {object_name}")
        endpoint = f"{base_url}/services/data/{self.api_version}/jobs/query"
        payload = {
            "operation": operation,
            "query": query
        }

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()

        result = await retry_call(
            _call,
            op_label=f"bulk_create_job_{object_name}",
            target_service="salesforce",
            payload=payload
        )
        logger.info(f"Created Bulk API job {result.get('id')} for {object_name} (state={result.get('state')})")
        return result

    async def get_job_status(
        self,
        job_id: str,
        creds: SalesforceCredentials
    ) -> Dict[str, Any]:
        """
        Poll query job execution state.
        GET /services/data/vXX.X/jobs/query/{job_id}
        States: UploadComplete, InProgress, JobComplete, Failed, Aborted
        """
        headers, base_url = await self._get_auth_headers(creds)
        endpoint = f"{base_url}/services/data/{self.api_version}/jobs/query/{job_id}"

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(endpoint, headers=headers)
                resp.raise_for_status()
                return resp.json()

        return await retry_call(
            _call,
            op_label=f"bulk_get_status_{job_id}",
            target_service="salesforce"
        )

    async def get_job_results(
        self,
        job_id: str,
        creds: SalesforceCredentials,
        locator: Optional[str] = None,
        max_records: int = 50000
    ) -> Tuple[str, Optional[str]]:
        """
        Retrieve CSV query results.
        GET /services/data/vXX.X/jobs/query/{job_id}/results
        Returns (csv_text, next_locator).
        """
        headers, base_url = await self._get_auth_headers(creds)
        headers["Accept"] = "text/csv"
        endpoint = f"{base_url}/services/data/{self.api_version}/jobs/query/{job_id}/results"
        params = {"maxRecords": max_records}
        if locator:
            params["locator"] = locator

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(endpoint, headers=headers, params=params)
                resp.raise_for_status()
                next_loc = resp.headers.get("Sforce-Locator")
                if next_loc == "null" or not next_loc:
                    next_loc = None
                return resp.text, next_loc

        return await retry_call(
            _call,
            op_label=f"bulk_get_results_{job_id}",
            target_service="salesforce"
        )

    async def abort_job(
        self,
        job_id: str,
        creds: SalesforceCredentials
    ) -> Dict[str, Any]:
        """
        Abort a running Bulk API job.
        PATCH /services/data/vXX.X/jobs/query/{job_id} {"state": "Aborted"}
        """
        headers, base_url = await self._get_auth_headers(creds)
        endpoint = f"{base_url}/services/data/{self.api_version}/jobs/query/{job_id}"
        payload = {"state": "Aborted"}

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.patch(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_call(
                _call,
                op_label=f"bulk_abort_{job_id}",
                target_service="salesforce",
                payload=payload
            )
        except Exception as exc:
            logger.warning(f"Failed to remotely abort Bulk API job {job_id}: {exc}")
            return {"id": job_id, "state": "AbortFailed", "error": str(exc)}


sf_batch_client = SalesforceBatchAPIClient()
