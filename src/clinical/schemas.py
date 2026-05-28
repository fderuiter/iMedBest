from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from uuid import UUID

class EntityPayload(BaseModel):
    entity_type: str
    hierarchy_level: int
    payload: Dict[str, Any]

class SyncJobRequest(BaseModel):
    entities: List[EntityPayload]

class SyncJobResponse(BaseModel):
    job_id: UUID
    status: str
    message: str
