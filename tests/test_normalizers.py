import os
import tempfile
import pandas as pd
import pytest

from app.services.normalization.base import BaseNormalizer
from app.services.normalization.accounts import AccountNormalizer
from app.services.normalization.contacts import ContactNormalizer
from app.services.normalization.opportunities import OpportunityNormalizer
from app.services.normalization.leads import LeadNormalizer
from app.services.normalization.cases import CaseNormalizer
from app.services.normalization.tasks_events import TaskEventNormalizer
from app.services.normalization.campaigns import CampaignNormalizer
from app.services.normalization.users import UserNormalizer
from app.services.normalization import get_normalizer, SUPPORTED_OBJECT_CATALOG


def test_base_normalizer_sanitization():
    class DummyNormalizer(BaseNormalizer):
        def normalize(self, records):
            return {"dummy": records}

    norm = DummyNormalizer()

    # safe_get case-insensitivity
    rec = {"FirstName": "Alice", "AGE": "30", "is_active": "true"}
    assert norm.safe_get(rec, "firstname") == "Alice"
    assert norm.safe_get(rec, ["NonExistent", "age"]) == "30"
    assert norm.safe_get(rec, "missing", "default_val") == "default_val"

    # clean_string
    assert norm.clean_string("  hello world  ") == "hello world"
    assert norm.clean_string("   ") is None
    assert norm.clean_string(None) is None

    # clean_bool
    assert norm.clean_bool("True") is True
    assert norm.clean_bool("1") is True
    assert norm.clean_bool("False") is False
    assert norm.clean_bool("0") is False
    assert norm.clean_bool("") is None
    assert norm.clean_bool(None) is None

    # clean_int
    assert norm.clean_int("42") == 42
    assert norm.clean_int("42.0") == 42
    assert norm.clean_int("invalid") is None
    assert norm.clean_int(None) is None

    # clean_float
    assert norm.clean_float("$1,234.56") == 1234.56
    assert norm.clean_float("0.95") == 0.95
    assert norm.clean_float("N/A") is None

    # clean_date
    assert "2026-10-25" in norm.clean_date("2026-10-25T12:00:00.000+0000")
    assert "2026-10-25" in norm.clean_date("2026-10-25")
    assert norm.clean_date(None) is None


def test_account_normalizer():
    normalizer = AccountNormalizer()
    raw_records = [
        {
            "Id": "001xx000003DGb2AAG",
            "Name": "Acme Corp",
            "AccountNumber": "AC-1001",
            "Type": "Customer - Direct",
            "Industry": "Technology",
            "AnnualRevenue": "$5,000,000.00",
            "NumberOfEmployees": "250",
            "BillingStreet": "123 Tech Way",
            "BillingCity": "San Francisco",
            "BillingState": "CA",
            "BillingPostalCode": "94105",
            "BillingCountry": "USA",
            "ShippingStreet": "456 Warehouse Rd",
            "ShippingCity": "Oakland",
            "ShippingState": "CA",
            "ShippingPostalCode": "94607",
            "ShippingCountry": "USA",
            "TeamMemberId": "005xx000001SvZ",
            "TeamMemberRole": "Account Manager"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert "accounts" in tables
    assert "account_addresses" in tables
    assert "account_teams" in tables

    # Check accounts table
    accounts = tables["accounts"]
    assert len(accounts) == 1
    assert accounts[0]["account_id"] == "001xx000003DGb2AAG"
    assert accounts[0]["name"] == "Acme Corp"
    assert accounts[0]["annual_revenue"] == 5000000.0
    assert accounts[0]["number_of_employees"] == 250

    # Check account_addresses table (separated billing and shipping addresses)
    addresses = tables["account_addresses"]
    assert len(addresses) == 2
    types = [addr["address_type"] for addr in addresses]
    assert "billing" in types
    assert "shipping" in types
    billing_addr = next(a for a in addresses if a["address_type"] == "billing")
    assert billing_addr["city"] == "San Francisco"
    assert billing_addr["postal_code"] == "94105"

    # Check account_teams table
    teams = tables["account_teams"]
    assert len(teams) == 1
    assert teams[0]["team_member_id"] == "005xx000001SvZ"
    assert teams[0]["team_role"] == "Account Manager"


def test_contact_normalizer():
    normalizer = ContactNormalizer()
    raw_records = [
        {
            "Id": "003xx000004TmiQAAS",
            "AccountId": "001xx000003DGb2AAG",
            "FirstName": "Jane",
            "LastName": "Doe",
            "Email": "jane.doe@example.com",
            "Phone": "+1-555-0199",
            "MailingStreet": "123 Tech Way",
            "MailingCity": "San Francisco",
            "Role": "Decision Maker",
            "IsPrimary": "true"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["contacts"]) == 1
    contact = tables["contacts"][0]
    assert contact["contact_id"] == "003xx000004TmiQAAS"
    assert contact["first_name"] == "Jane"
    assert contact["last_name"] == "Doe"
    assert contact["name"] == "Jane Doe"
    assert contact["email"] == "jane.doe@example.com"

    assert len(tables["contact_roles"]) == 1
    role = tables["contact_roles"][0]
    assert role["role"] == "Decision Maker"
    assert role["is_primary"] is True


def test_opportunity_normalizer():
    normalizer = OpportunityNormalizer()
    raw_records = [
        {
            "Id": "006xx000001SABC",
            "AccountId": "001xx000003DGb2AAG",
            "Name": "Cloud Migration Deal",
            "StageName": "Closed Won",
            "Amount": "75000.00",
            "Probability": "100",
            "IsWon": "true",
            "IsClosed": "true",
            "CloseDate": "2026-11-01"
        },
        {
            "Id": "00kxx000001LineItem",
            "OpportunityId": "006xx000001SABC",
            "ProductCode": "CLOUD-PRO",
            "Quantity": "5",
            "UnitPrice": "15000",
            "TotalPrice": "75000"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["opportunities"]) == 1
    opp = tables["opportunities"][0]
    assert opp["opportunity_id"] == "006xx000001SABC"
    assert opp["stage_name"] == "Closed Won"
    assert opp["amount"] == 75000.0
    assert opp["is_won"] is True

    assert len(tables["opportunity_line_items"]) == 1
    li = tables["opportunity_line_items"][0]
    assert li["line_item_id"] == "00kxx000001LineItem"
    assert li["quantity"] == 5.0
    assert li["total_price"] == 75000.0


def test_lead_normalizer():
    normalizer = LeadNormalizer()
    raw_records = [
        {
            "Id": "00Qxx000001Lead1",
            "FirstName": "Bob",
            "LastName": "Smith",
            "Company": "Innovate LLC",
            "Email": "bob@innovate.com",
            "Status": "Working - Contacted",
            "AnnualRevenue": "250000",
            "IsConverted": "false"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["leads"]) == 1
    lead = tables["leads"][0]
    assert lead["lead_id"] == "00Qxx000001Lead1"
    assert lead["company"] == "Innovate LLC"
    assert lead["status"] == "Working - Contacted"
    assert lead["annual_revenue"] == 250000.0
    assert lead["is_converted"] is False


def test_case_normalizer():
    normalizer = CaseNormalizer()
    raw_records = [
        {
            "Id": "500xx000001Case1",
            "CaseNumber": "0001023",
            "Subject": "Cannot configure OAuth integration",
            "Priority": "High",
            "Status": "New",
            "IsClosed": "false",
            "Comments": "Customer reported timeout when connecting to API."
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["cases"]) == 1
    c = tables["cases"][0]
    assert c["case_id"] == "500xx000001Case1"
    assert c["priority"] == "High"
    assert c["is_closed"] is False

    assert len(tables["case_comments"]) == 1
    comment = tables["case_comments"][0]
    assert "timeout when connecting" in comment["comment_body"]


def test_task_event_normalizer():
    normalizer = TaskEventNormalizer()
    raw_records = [
        {
            "Id": "00Txx000001Task1",
            "Subject": "Follow-up Call",
            "Status": "Completed",
            "Priority": "Normal",
            "IsClosed": "true"
        },
        {
            "Id": "00Uxx000001Event1",
            "Subject": "Executive Quarterly Business Review",
            "StartDateTime": "2026-11-15T10:00:00Z",
            "EndDateTime": "2026-11-15T11:30:00Z",
            "DurationInMinutes": "90",
            "Location": "Boardroom A"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["tasks"]) == 1
    assert tables["tasks"][0]["task_id"] == "00Txx000001Task1"
    assert tables["tasks"][0]["is_closed"] is True

    assert len(tables["events"]) == 1
    assert tables["events"][0]["event_id"] == "00Uxx000001Event1"
    assert tables["events"][0]["duration_in_minutes"] == 90
    assert tables["events"][0]["location"] == "Boardroom A"


def test_campaign_normalizer():
    normalizer = CampaignNormalizer()
    raw_records = [
        {
            "Id": "701xx000001Camp1",
            "Name": "Q4 Enterprise SaaS Campaign",
            "Type": "Webinar",
            "Status": "In Progress",
            "BudgetedCost": "10000",
            "ActualCost": "8500",
            "ExpectedRevenue": "50000",
            "IsActive": "true"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["campaigns"]) == 1
    camp = tables["campaigns"][0]
    assert camp["campaign_id"] == "701xx000001Camp1"
    assert camp["budgeted_cost"] == 10000.0
    assert camp["actual_cost"] == 8500.0
    assert camp["is_active"] is True


def test_user_normalizer():
    normalizer = UserNormalizer()
    raw_records = [
        {
            "Id": "005xx000001User1",
            "Username": "admin@salesforce-demo.org",
            "FirstName": "Admin",
            "LastName": "User",
            "Email": "admin@salesforce-demo.org",
            "Title": "System Administrator",
            "IsActive": "true"
        }
    ]

    tables = normalizer.normalize(raw_records)
    assert len(tables["users"]) == 1
    user = tables["users"][0]
    assert user["user_id"] == "005xx000001User1"
    assert user["email"] == "admin@salesforce-demo.org"
    assert user["is_active"] is True


def test_parquet_and_json_file_export():
    normalizer = AccountNormalizer()
    records = [
        {"Id": "001A", "Name": "Corp A", "BillingCity": "Austin", "BillingCountry": "USA"},
        {"Id": "001B", "Name": "Corp B", "BillingCity": "Dallas", "BillingCountry": "USA"}
    ]
    tables = normalizer.normalize(records)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test Parquet export
        parquet_stats = normalizer.save_to_files(tables, temp_dir, format="parquet")
        assert "accounts" in parquet_stats
        assert os.path.exists(parquet_stats["accounts"]["file_path"])
        assert parquet_stats["accounts"]["row_count"] == 2

        # Verify Parquet content can be read back accurately
        df_accounts = pd.read_parquet(parquet_stats["accounts"]["file_path"])
        assert len(df_accounts) == 2
        assert "account_id" in df_accounts.columns
        assert df_accounts["name"].tolist() == ["Corp A", "Corp B"]

        # Test JSON export
        json_stats = normalizer.save_to_files(tables, temp_dir, format="json")
        assert "accounts" in json_stats
        assert os.path.exists(json_stats["accounts"]["file_path"])
        assert json_stats["accounts"]["row_count"] == 2


def test_registry_and_catalog():
    assert get_normalizer("Account") is not None
    assert get_normalizer("contact") is not None
    assert get_normalizer("opportunity") is not None
    assert get_normalizer("Lead") is not None
    assert get_normalizer("case") is not None
    assert get_normalizer("task") is not None
    assert get_normalizer("event") is not None
    assert get_normalizer("user") is not None
    assert len(SUPPORTED_OBJECT_CATALOG) >= 8
