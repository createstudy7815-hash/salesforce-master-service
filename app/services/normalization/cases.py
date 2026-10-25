import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class CaseNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Case records into:
    1. cases: Clean, flat support cases table
    2. case_comments: Comments associated with cases (if present or extracted)
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        cases: List[Dict[str, Any]] = []
        case_comments: List[Dict[str, Any]] = []

        for row in records:
            case_id = self.safe_get(row, ["Id", "case_id", "CaseId"])
            if not case_id:
                continue

            # Check if this record is a CaseComment directly
            if "CommentBody" in row or "comment_body" in row:
                comment_id = self.safe_get(row, ["Id", "comment_id"])
                parent_case_id = self.safe_get(row, ["ParentId", "case_id"]) or case_id
                case_comments.append({
                    "comment_id": self.clean_string(comment_id),
                    "case_id": self.clean_string(parent_case_id),
                    "is_published": self.clean_bool(self.safe_get(row, ["IsPublished", "is_published"], False)),
                    "comment_body": self.clean_string(self.safe_get(row, ["CommentBody", "comment_body"])),
                    "created_by_id": self.clean_string(self.safe_get(row, ["CreatedById", "created_by_id"])),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"]))
                })
                # If row only contains comment data, skip case generation
                if not any(k in row for k in ["CaseNumber", "Subject", "Priority", "Status"]):
                    continue

            # Core Case record
            cases.append({
                "case_id": self.clean_string(case_id),
                "case_number": self.clean_string(self.safe_get(row, ["CaseNumber", "case_number"])),
                "contact_id": self.clean_string(self.safe_get(row, ["ContactId", "contact_id"])),
                "account_id": self.clean_string(self.safe_get(row, ["AccountId", "account_id"])),
                "parent_id": self.clean_string(self.safe_get(row, ["ParentId", "parent_id"])),
                "supplied_name": self.clean_string(self.safe_get(row, ["SuppliedName", "supplied_name"])),
                "supplied_email": self.clean_string(self.safe_get(row, ["SuppliedEmail", "supplied_email"])),
                "supplied_phone": self.clean_string(self.safe_get(row, ["SuppliedPhone", "supplied_phone"])),
                "supplied_company": self.clean_string(self.safe_get(row, ["SuppliedCompany", "supplied_company"])),
                "type": self.clean_string(self.safe_get(row, ["Type", "type"])),
                "status": self.clean_string(self.safe_get(row, ["Status", "status"])),
                "reason": self.clean_string(self.safe_get(row, ["Reason", "reason"])),
                "origin": self.clean_string(self.safe_get(row, ["Origin", "origin"])),
                "subject": self.clean_string(self.safe_get(row, ["Subject", "subject"])),
                "priority": self.clean_string(self.safe_get(row, ["Priority", "priority"])),
                "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                "is_closed": self.clean_bool(self.safe_get(row, ["IsClosed", "is_closed"])),
                "closed_date": self.clean_date(self.safe_get(row, ["ClosedDate", "closed_date"])),
                "is_escalated": self.clean_bool(self.safe_get(row, ["IsEscalated", "is_escalated"])),
                "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
            })

            # Check if inline comment body is on the Case row
            inline_comment = self.clean_string(self.safe_get(row, ["Comments", "comments"]))
            if inline_comment:
                case_comments.append({
                    "comment_id": f"{case_id}_comment",
                    "case_id": case_id,
                    "is_published": False,
                    "comment_body": inline_comment,
                    "created_by_id": self.clean_string(self.safe_get(row, ["CreatedById", "created_by_id"])),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"]))
                })

        return {
            "cases": cases,
            "case_comments": case_comments
        }
