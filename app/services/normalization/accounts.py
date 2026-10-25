import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class AccountNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Account records into:
    1. accounts: Clean, flat core account entity
    2. account_addresses: Separated billing and shipping address records
    3. account_teams: Account team assignments (if present)
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        accounts: List[Dict[str, Any]] = []
        addresses: List[Dict[str, Any]] = []
        teams: List[Dict[str, Any]] = []

        for row in records:
            acc_id = self.safe_get(row, ["Id", "account_id"])
            if not acc_id:
                continue

            # Core Account Record
            accounts.append({
                "account_id": self.clean_string(acc_id),
                "name": self.clean_string(self.safe_get(row, ["Name", "name"])),
                "account_number": self.clean_string(self.safe_get(row, ["AccountNumber", "account_number"])),
                "type": self.clean_string(self.safe_get(row, ["Type", "type"])),
                "parent_id": self.clean_string(self.safe_get(row, ["ParentId", "parent_id"])),
                "industry": self.clean_string(self.safe_get(row, ["Industry", "industry"])),
                "annual_revenue": self.clean_float(self.safe_get(row, ["AnnualRevenue", "annual_revenue"])),
                "number_of_employees": self.clean_int(self.safe_get(row, ["NumberOfEmployees", "number_of_employees"])),
                "ownership": self.clean_string(self.safe_get(row, ["Ownership", "ownership"])),
                "ticker_symbol": self.clean_string(self.safe_get(row, ["TickerSymbol", "ticker_symbol"])),
                "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                "rating": self.clean_string(self.safe_get(row, ["Rating", "rating"])),
                "phone": self.clean_string(self.safe_get(row, ["Phone", "phone"])),
                "fax": self.clean_string(self.safe_get(row, ["Fax", "fax"])),
                "website": self.clean_string(self.safe_get(row, ["Website", "website"])),
                "sic_code": self.clean_string(self.safe_get(row, ["Sic", "sic_code"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "created_by_id": self.clean_string(self.safe_get(row, ["CreatedById", "created_by_id"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"])),
                "last_modified_by_id": self.clean_string(self.safe_get(row, ["LastModifiedById", "last_modified_by_id"])),
                "system_modstamp": self.clean_date(self.safe_get(row, ["SystemModstamp", "system_modstamp"]))
            })

            # Billing Address
            b_street = self.clean_string(self.safe_get(row, ["BillingStreet", "billing_street"]))
            b_city = self.clean_string(self.safe_get(row, ["BillingCity", "billing_city"]))
            b_state = self.clean_string(self.safe_get(row, ["BillingState", "billing_state"]))
            b_postal = self.clean_string(self.safe_get(row, ["BillingPostalCode", "billing_postal_code"]))
            b_country = self.clean_string(self.safe_get(row, ["BillingCountry", "billing_country"]))

            if any([b_street, b_city, b_state, b_postal, b_country]):
                addresses.append({
                    "address_id": f"{acc_id}_billing",
                    "account_id": acc_id,
                    "address_type": "billing",
                    "street": b_street,
                    "city": b_city,
                    "state": b_state,
                    "postal_code": b_postal,
                    "country": b_country
                })

            # Shipping Address
            s_street = self.clean_string(self.safe_get(row, ["ShippingStreet", "shipping_street"]))
            s_city = self.clean_string(self.safe_get(row, ["ShippingCity", "shipping_city"]))
            s_state = self.clean_string(self.safe_get(row, ["ShippingState", "shipping_state"]))
            s_postal = self.clean_string(self.safe_get(row, ["ShippingPostalCode", "shipping_postal_code"]))
            s_country = self.clean_string(self.safe_get(row, ["ShippingCountry", "shipping_country"]))

            if any([s_street, s_city, s_state, s_postal, s_country]):
                addresses.append({
                    "address_id": f"{acc_id}_shipping",
                    "account_id": acc_id,
                    "address_type": "shipping",
                    "street": s_street,
                    "city": s_city,
                    "state": s_state,
                    "postal_code": s_postal,
                    "country": s_country
                })

            # Account Team (if row contains team fields or team member data)
            team_member_id = self.clean_string(self.safe_get(row, ["TeamMemberId", "team_member_id", "UserId"]))
            if team_member_id:
                teams.append({
                    "team_id": self.clean_string(self.safe_get(row, ["TeamId", "team_id", "Id"], f"{acc_id}_{team_member_id}")),
                    "account_id": acc_id,
                    "team_member_id": team_member_id,
                    "team_role": self.clean_string(self.safe_get(row, ["TeamMemberRole", "team_role"], "Member")),
                    "access_level": self.clean_string(self.safe_get(row, ["AccountAccessLevel", "access_level"], "Read"))
                })

        return {
            "accounts": accounts,
            "account_addresses": addresses,
            "account_teams": teams
        }
