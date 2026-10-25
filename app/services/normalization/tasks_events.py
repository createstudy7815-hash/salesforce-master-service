import logging
from typing import Dict, List, Any
from app.services.normalization.base import BaseNormalizer

logger = logging.getLogger(__name__)


class TaskEventNormalizer(BaseNormalizer):
    """
    Normalizes Salesforce Activity records into:
    1. tasks: To-do items, calls, reminders
    2. events: Calendar events and meetings
    """

    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        tasks: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []

        for row in records:
            rec_id = self.safe_get(row, ["Id", "task_id", "event_id", "activity_id"])
            if not rec_id:
                continue

            # Determine whether record is an Event or a Task
            # Events have StartDateTime, EndDateTime, DurationInMinutes, or IsAllDayEvent
            is_event = any(k in row for k in ["StartDateTime", "EndDateTime", "DurationInMinutes", "IsAllDayEvent"]) or \
                       str(self.safe_get(row, ["type", "Type"], "")).lower() == "event"

            if is_event:
                events.append({
                    "event_id": self.clean_string(rec_id),
                    "who_id": self.clean_string(self.safe_get(row, ["WhoId", "who_id"])),
                    "what_id": self.clean_string(self.safe_get(row, ["WhatId", "what_id"])),
                    "subject": self.clean_string(self.safe_get(row, ["Subject", "subject"])),
                    "location": self.clean_string(self.safe_get(row, ["Location", "location"])),
                    "is_all_day_event": self.clean_bool(self.safe_get(row, ["IsAllDayEvent", "is_all_day_event"], False)),
                    "activity_date_time": self.clean_date(self.safe_get(row, ["ActivityDateTime", "activity_date_time"])),
                    "activity_date": self.clean_date(self.safe_get(row, ["ActivityDate", "activity_date"])),
                    "duration_in_minutes": self.clean_int(self.safe_get(row, ["DurationInMinutes", "duration_in_minutes"])),
                    "start_date_time": self.clean_date(self.safe_get(row, ["StartDateTime", "start_date_time"])),
                    "end_date_time": self.clean_date(self.safe_get(row, ["EndDateTime", "end_date_time"])),
                    "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                    "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                    "type": self.clean_string(self.safe_get(row, ["EventSubtype", "Type", "type"])),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                    "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
                })
            else:
                tasks.append({
                    "task_id": self.clean_string(rec_id),
                    "who_id": self.clean_string(self.safe_get(row, ["WhoId", "who_id"])),
                    "what_id": self.clean_string(self.safe_get(row, ["WhatId", "what_id"])),
                    "subject": self.clean_string(self.safe_get(row, ["Subject", "subject"])),
                    "activity_date": self.clean_date(self.safe_get(row, ["ActivityDate", "activity_date"])),
                    "status": self.clean_string(self.safe_get(row, ["Status", "status"])),
                    "priority": self.clean_string(self.safe_get(row, ["Priority", "priority"])),
                    "is_high_priority": self.clean_bool(self.safe_get(row, ["IsHighPriority", "is_high_priority"], False)),
                    "owner_id": self.clean_string(self.safe_get(row, ["OwnerId", "owner_id"])),
                    "description": self.clean_string(self.safe_get(row, ["Description", "description"])),
                    "type": self.clean_string(self.safe_get(row, ["TaskSubtype", "Type", "type"])),
                    "is_closed": self.clean_bool(self.safe_get(row, ["IsClosed", "is_closed"], False)),
                    "created_date": self.clean_date(self.safe_get(row, ["CreatedDate", "created_date"])),
                    "last_modified_date": self.clean_date(self.safe_get(row, ["LastModifiedDate", "last_modified_date"]))
                })

        return {
            "tasks": tasks,
            "events": events
        }
