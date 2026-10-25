import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class CampaignNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Campaign records into:
    1. campaigns: Marketing campaigns and ROI metrics
    2. campaign_members: Leads/contacts enrolled in the campaign
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        campaigns: List[Dict[str, Any]] = []
        members: List[Dict[str, Any]] = []

        for row in records:
            camp_id = self.safe_get(row, ["Id", "campaign_id", "CampaignId"])
            if not camp_id:
                continue

            # Check if this row is directly a CampaignMember
            if "LeadId" in row or "ContactId" in row or "HasResponded" in row:
                member_id = self.safe_get(row, ["Id", "member_id"])
                parent_camp_id = self.safe_get(row, ["CampaignId", "campaign_id"]) or camp_id
                members.append({
                    "member_id": self.clean_string(member_id),
                    "campaign_id": self.clean_string(parent_camp_id),
                    "lead_id": self.clean_string(self.safe_get(row, ["LeadId", "lead_id"])),
                    "contact_id": self.clean_string(self.safe_get(row, ["ContactId", "contact_id"])),
                    "status": self.clean_string(self.safe_get(row, ["Status", "status"])),
                    "has_responded": self.clean_bool(self.safe_get(row, ["HasResponded", "has_responded"], False)),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"]))
                })
                # If row only has member fields, skip campaign row
                if not any(k in row for k in ["ExpectedRevenue", "BudgetedCost", "ActualCost", "StartDate"]):
                    continue

            campaigns.append({
                "campaign_id": self.clean_string(camp_id),
                "name": self.clean_string(self.safe_get(row, ["Name", "name"])),
                "type": self.clean_string(self.safe_get(row, ["Type", "type"])),
                "status": self.clean_string(self.safe_get(row, ["Status", "status"])),
                "start_date": self.clean_date(self.safe_get(row, ["StartDate", "start_date"])),
                "end_date": self.clean_date(self.safe_get(row, ["EndDate", "end_date"])),
                "expected_revenue": self.clean_float(self.safe_get(row, ["ExpectedRevenue", "expected_revenue"])),
                "budgeted_cost": self.clean_float(self.safe_get(row, ["BudgetedCost", "budgeted_cost"])),
                "actual_cost": self.clean_float(self.safe_get(row, ["ActualCost", "actual_cost"])),
                "expected_response": self.clean_float(self.safe_get(row, ["ExpectedResponse", "expected_response"])),
                "number_sent": self.clean_float(self.safe_get(row, ["NumberSent", "number_sent"])),
                "is_active": self.clean_bool(self.safe_get(row, ["IsActive", "is_active"], True)),
                "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                "number_of_leads": self.clean_int(self.safe_get(row, ["NumberOfLeads", "number_of_leads"])),
                "number_of_converted_leads": self.clean_int(self.safe_get(row, ["NumberOfConvertedLeads", "number_of_converted_leads"])),
                "number_of_contacts": self.clean_int(self.safe_get(row, ["NumberOfContacts", "number_of_contacts"])),
                "number_of_responses": self.clean_int(self.safe_get(row, ["NumberOfResponses", "number_of_responses"])),
                "number_of_opportunities": self.clean_int(self.safe_get(row, ["NumberOfOpportunities", "number_of_opportunities"])),
                "number_of_won_opportunities": self.clean_int(self.safe_get(row, ["NumberOfWonOpportunities", "number_of_won_opportunities"])),
                "amount_all_opportunities": self.clean_float(self.safe_get(row, ["AmountAllOpportunities", "amount_all_opportunities"])),
                "amount_won_opportunities": self.clean_float(self.safe_get(row, ["AmountWonOpportunities", "amount_won_opportunities"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

        return {
            "campaigns": campaigns,
            "campaign_members": members
        }
