import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class OpportunityNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Opportunity records into:
    1. opportunities: Core opportunity deals table
    2. opportunity_line_items: Deal line items/products (if present or extracted)
    3. opportunity_contact_roles: Deal stakeholders/roles
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        opportunities: List[Dict[str, Any]] = []
        line_items: List[Dict[str, Any]] = []
        contact_roles: List[Dict[str, Any]] = []

        for row in records:
            opp_id = self.safe_get(row, ["Id", "opportunity_id", "OpportunityId"])
            if not opp_id:
                continue

            # Check if this row is an OpportunityLineItem directly
            if "TotalPrice" in row or "UnitPrice" in row or "PricebookEntryId" in row or "Product2Id" in row:
                li_id = self.safe_get(row, ["Id", "line_item_id"])
                parent_opp_id = self.safe_get(row, ["OpportunityId", "opportunity_id"]) or opp_id
                line_items.append({
                    "line_item_id": self.clean_string(li_id),
                    "opportunity_id": self.clean_string(parent_opp_id),
                    "pricebook_entry_id": self.clean_string(self.safe_get(row, ["PricebookEntryId", "pricebook_entry_id"])),
                    "product2_id": self.clean_string(self.safe_get(row, ["Product2Id", "product2_id"])),
                    "product_code": self.clean_string(self.safe_get(row, ["ProductCode", "product_code"])),
                    "quantity": self.clean_float(self.safe_get(row, ["Quantity", "quantity"])),
                    "unit_price": self.clean_float(self.safe_get(row, ["UnitPrice", "unit_price"])),
                    "total_price": self.clean_float(self.safe_get(row, ["TotalPrice", "total_price"])),
                    "service_date": self.clean_date(self.safe_get(row, ["ServiceDate", "service_date"])),
                    "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"]))
                })
                # If row only contains line item fields, don't generate duplicate opportunity
                if not any(k in row for k in ["StageName", "CloseDate", "ForecastCategory"]):
                    continue

            # Core Opportunity record
            opportunities.append({
                "opportunity_id": self.clean_string(opp_id),
                "account_id": self.clean_string(self.safe_get(row, ["AccountId", "account_id"])),
                "name": self.clean_string(self.safe_get(row, ["Name", "name"])),
                "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                "stage_name": self.clean_string(self.safe_get(row, ["StageName", "stage_name"])),
                "amount": self.clean_float(self.safe_get(row, ["Amount", "amount"])),
                "probability": self.clean_float(self.safe_get(row, ["Probability", "probability"])),
                "expected_revenue": self.clean_float(self.safe_get(row, ["ExpectedRevenue", "expected_revenue"])),
                "close_date": self.clean_date(self.safe_get(row, ["CloseDate", "close_date"])),
                "type": self.clean_string(self.safe_get(row, ["Type", "type"])),
                "next_step": self.clean_string(self.safe_get(row, ["NextStep", "next_step"])),
                "lead_source": self.clean_string(self.safe_get(row, ["LeadSource", "lead_source"])),
                "is_closed": self.clean_bool(self.safe_get(row, ["IsClosed", "is_closed"])),
                "is_won": self.clean_bool(self.safe_get(row, ["IsWon", "is_won"])),
                "forecast_category": self.clean_string(self.safe_get(row, ["ForecastCategory", "forecast_category"])),
                "forecast_category_name": self.clean_string(self.safe_get(row, ["ForecastCategoryName", "forecast_category_name"])),
                "campaign_id": self.clean_string(self.safe_get(row, ["CampaignId", "campaign_id"])),
                "pricebook2_id": self.clean_string(self.safe_get(row, ["Pricebook2Id", "pricebook2_id"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

            # Check if contact role on opportunity is present
            contact_id = self.clean_string(self.safe_get(row, ["ContactId", "contact_id"]))
            if contact_id:
                contact_roles.append({
                    "role_id": self.clean_string(self.safe_get(row, ["ContactRoleId", "role_id"], f"{opp_id}_{contact_id}")),
                    "opportunity_id": opp_id,
                    "contact_id": contact_id,
                    "role": self.clean_string(self.safe_get(row, ["Role", "role"], "Decision Maker")),
                    "is_primary": self.clean_bool(self.safe_get(row, ["IsPrimary", "is_primary"], False))
                })

        return {
            "opportunities": opportunities,
            "opportunity_line_items": line_items,
            "opportunity_contact_roles": contact_roles
        }
