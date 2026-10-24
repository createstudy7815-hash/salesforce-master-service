from typing import List, Dict
from pydantic import BaseModel


class BatchInfoResponse(BaseModel):
    api_version: str
    supported_objects: List[str]
    default_poll_interval_seconds: int
    max_wait_minutes: int
    query_defaults: Dict[str, str]
