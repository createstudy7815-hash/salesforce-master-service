import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class LeadNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Lead records into a clean, flat leads table.
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        leads: List[Dict[str, Any]] = []

        for row in records:
            lead_id = self.safe_get(row, ["Id", "lead_id"])
            if not lead_id:
                continue

            first_name = self.clean_string(self.safe_get(row, ["FirstName", "first_name"]))
            last_name = self.clean_string(self.safe_get(row, ["LastName", "last_name"]))
            full_name = self.clean_string(self.safe_get(row, ["Name", "name"])) or f"{first_name or ''} {last_name or ''}".strip()

            leads.append({
                "lead_id": self.clean_string(lead_id),
                "first_name": first_name,
                "last_name": last_name,
                "salutation": self.clean_string(self.safe_get(row, ["Salutation", "salutation"])),
                "name": full_name,
                "title": self.clean_string(self.safe_get(row, ["Title", "title"])),
                "company": self.clean_string(self.safe_get(row, ["Company", "company"])),
                "street": self.clean_string(self.safe_get(row, ["Street", "street"])),
                "city": self.clean_string(self.safe_get(row, ["City", "city"])),
                "state": self.clean_string(self.safe_get(row, ["State", "state"])),
                "postal_code": self.clean_string(self.safe_get(row, ["PostalCode", "postal_code"])),
                "country": self.clean_string(self.safe_get(row, ["Country", "country"])),
                "phone": self.clean_string(self.safe_get(row, ["Phone", "phone"])),
                "mobile_phone": self.clean_string(self.safe_get(row, ["MobilePhone", "mobile_phone"])),
                "email": self.clean_string(self.safe_get(row, ["Email", "email"])),
                "website": self.clean_string(self.safe_get(row, ["Website", "website"])),
                "lead_source": self.clean_string(self.safe_get(row, ["LeadSource", "lead_source"])),
                "status": self.clean_string(self.safe_get(row, ["Status", "status"])),
                "industry": self.clean_string(self.safe_get(row, ["Industry", "industry"])),
                "rating": self.clean_string(self.safe_get(row, ["Rating", "rating"])),
                "annual_revenue": self.clean_float(self.safe_get(row, ["AnnualRevenue", "annual_revenue"])),
                "number_of_employees": self.clean_int(self.safe_get(row, ["NumberOfEmployees", "number_of_employees"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "is_converted": self.clean_bool(self.safe_get(row, ["IsConverted", "is_converted"])),
                "converted_date": self.clean_date(self.safe_get(row, ["ConvertedDate", "converted_date"])),
                "converted_account_id": self.clean_string(self.safe_get(row, ["ConvertedAccountId", "converted_account_id"])),
                "converted_contact_id": self.clean_string(self.safe_get(row, ["ConvertedContactId", "converted_contact_id"])),
                "converted_opportunity_id": self.clean_string(self.safe_get(row, ["ConvertedOpportunityId", "converted_opportunity_id"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

        return {
            "leads": leads
        }
