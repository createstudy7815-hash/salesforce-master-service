from typing import Dict, Optional, List
from app.services.normalization.base import BaseNormalizer
from app.services.normalization.accounts import AccountNormalizer
from app.services.normalization.contacts import ContactNormalizer
from app.services.normalization.opportunities import OpportunityNormalizer
from app.services.normalization.leads import LeadNormalizer
from app.services.normalization.cases import CaseNormalizer
from app.services.normalization.tasks_events import TaskEventNormalizer
from app.services.normalization.campaigns import CampaignNormalizer
from app.services.normalization.users import UserNormalizer

NORMALIZER_REGISTRY: Dict[str, BaseNormalizer] = {
    "account": AccountNormalizer(),
    "contact": ContactNormalizer(),
    "opportunity": OpportunityNormalizer(),
    "opportunitylineitem": OpportunityNormalizer(),
    "lead": LeadNormalizer(),
    "case": CaseNormalizer(),
    "casecomment": CaseNormalizer(),
    "task": TaskEventNormalizer(),
    "event": TaskEventNormalizer(),
    "campaign": CampaignNormalizer(),
    "campaignmember": CampaignNormalizer(),
    "user": UserNormalizer()
}

SUPPORTED_OBJECT_CATALOG = [
    {
        "object_name": "Account",
        "target_tables": ["accounts", "account_addresses", "account_teams"],
        "description": "Flattens Account records, extracts normalized billing/shipping addresses, and maps team roles."
    },
    {
        "object_name": "Contact",
        "target_tables": ["contacts", "contact_roles"],
        "description": "Flattens Contact records, cleans phone/email fields, and structures contact roles."
    },
    {
        "object_name": "Opportunity",
        "target_tables": ["opportunities", "opportunity_line_items", "opportunity_contact_roles"],
        "description": "Flattens deal pipelines, line items, products, and deal stakeholders."
    },
    {
        "object_name": "Lead",
        "target_tables": ["leads"],
        "description": "Flattens sales leads and tracks conversion outcomes."
    },
    {
        "object_name": "Case",
        "target_tables": ["cases", "case_comments"],
        "description": "Flattens customer support cases and related case comments."
    },
    {
        "object_name": "Task",
        "target_tables": ["tasks"],
        "description": "Flattens action items, calls, and follow-ups."
    },
    {
        "object_name": "Event",
        "target_tables": ["events"],
        "description": "Flattens meetings, conferences, and calendar events."
    },
    {
        "object_name": "Campaign",
        "target_tables": ["campaigns", "campaign_members"],
        "description": "Flattens marketing campaigns, ROI metrics, and campaign memberships."
    },
    {
        "object_name": "User",
        "target_tables": ["users"],
        "description": "Flattens Salesforce organization users and profile references."
    }
]


def get_normalizer(object_name: str) -> Optional[BaseNormalizer]:
    """Get normalizer instance for a Salesforce object name (case-insensitive)."""
    return NORMALIZER_REGISTRY.get(object_name.lower())
