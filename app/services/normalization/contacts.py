import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class ContactNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Contact records into:
    1. contacts: Clean flat contact table
    2. contact_roles: Associated role relationships
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        contacts: List[Dict[str, Any]] = []
        contact_roles: List[Dict[str, Any]] = []

        for row in records:
            contact_id = self.safe_get(row, ["Id", "contact_id"])
            if not contact_id:
                continue

            first_name = self.clean_string(self.safe_get(row, ["FirstName", "first_name"]))
            last_name = self.clean_string(self.safe_get(row, ["LastName", "last_name"]))
            full_name = self.clean_string(self.safe_get(row, ["Name", "name"])) or f"{first_name or ''} {last_name or ''}".strip()

            contacts.append({
                "contact_id": self.clean_string(contact_id),
                "account_id": self.clean_string(self.safe_get(row, ["AccountId", "account_id"])),
                "first_name": first_name,
                "last_name": last_name,
                "salutation": self.clean_string(self.safe_get(row, ["Salutation", "salutation"])),
                "name": full_name,
                "title": self.clean_string(self.safe_get(row, ["Title", "title"])),
                "department": self.clean_string(self.safe_get(row, ["Department", "department"])),
                "email": self.clean_string(self.safe_get(row, ["Email", "email"])),
                "phone": self.clean_string(self.safe_get(row, ["Phone", "phone"])),
                "mobile_phone": self.clean_string(self.safe_get(row, ["MobilePhone", "mobile_phone"])),
                "fax": self.clean_string(self.safe_get(row, ["Fax", "fax"])),
                "lead_source": self.clean_string(self.safe_get(row, ["LeadSource", "lead_source"])),
                "birthdate": self.clean_date(self.safe_get(row, ["Birthdate", "birthdate"])),
                "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "mailing_street": self.clean_string(self.safe_get(row, ["MailingStreet", "mailing_street"])),
                "mailing_city": self.clean_string(self.safe_get(row, ["MailingCity", "mailing_city"])),
                "mailing_state": self.clean_string(self.safe_get(row, ["MailingState", "mailing_state"])),
                "mailing_postal_code": self.clean_string(self.safe_get(row, ["MailingPostalCode", "mailing_postal_code"])),
                "mailing_country": self.clean_string(self.safe_get(row, ["MailingCountry", "mailing_country"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

            # Check if contact role information is present
            role = self.clean_string(self.safe_get(row, ["Role", "role", "ContactRole"]))
            if role:
                contact_roles.append({
                    "role_id": self.clean_string(self.safe_get(row, ["RoleId", "role_id"], f"{contact_id}_{role}")),
                    "contact_id": contact_id,
                    "account_id": self.clean_string(self.safe_get(row, ["AccountId", "account_id"])),
                    "role": role,
                    "is_primary": self.clean_bool(self.safe_get(row, ["IsPrimary", "is_primary"], False))
                })

        return {
            "contacts": contacts,
            "contact_roles": contact_roles
        }
