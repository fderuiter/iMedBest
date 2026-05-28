from typing import Any
from uuid import UUID

from pydantic import BaseModel


class EntityPayload(BaseModel):
    entity_type: str
    hierarchy_level: int
    payload: dict[str, Any]

class SyncJobRequest(BaseModel):
    entities: list[EntityPayload]

class SyncJobResponse(BaseModel):
    job_id: UUID
    status: str
    message: str
