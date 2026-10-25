import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class UserNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce User records into a clean, flat users table.
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        users: List[Dict[str, Any]] = []

        for row in records:
            user_id = self.safe_get(row, ["Id", "user_id"])
            if not user_id:
                continue

            first_name = self.clean_string(self.safe_get(row, ["FirstName", "first_name"]))
            last_name = self.clean_string(self.safe_get(row, ["LastName", "last_name"]))
            full_name = self.clean_string(self.safe_get(row, ["Name", "name"])) or f"{first_name or ''} {last_name or ''}".strip()

            users.append({
                "user_id": self.clean_string(user_id),
                "username": self.clean_string(self.safe_get(row, ["Username", "username"])),
                "first_name": first_name,
                "last_name": last_name,
                "name": full_name,
                "email": self.clean_string(self.safe_get(row, ["Email", "email"])),
                "phone": self.clean_string(self.safe_get(row, ["Phone", "phone"])),
                "mobile_phone": self.clean_string(self.safe_get(row, ["MobilePhone", "mobile_phone"])),
                "title": self.clean_string(self.safe_get(row, ["Title", "title"])),
                "department": self.clean_string(self.safe_get(row, ["Department", "department"])),
                "division": self.clean_string(self.safe_get(row, ["Division", "division"])),
                "company_name": self.clean_string(self.safe_get(row, ["CompanyName", "company_name"])),
                "alias": self.clean_string(self.safe_get(row, ["Alias", "alias"])),
                "is_active": self.clean_bool(self.safe_get(row, ["IsActive", "is_active"], True)),
                "user_role_id": self.clean_string(self.safe_get(row, ["UserRoleId", "user_role_id"])),
                "profile_id": self.clean_string(self.safe_get(row, ["ProfileId", "profile_id"])),
                "user_type": self.clean_string(self.safe_get(row, ["UserType", "user_type"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

        return {
            "users": users
        }
