import re
from typing import Any
from uuid import UUID

from ninja import Schema as BaseModel
from pydantic import model_validator


def _camel_to_snake(name: str) -> str:
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def _convert_dict_keys(d: dict[str, Any]) -> dict[str, Any]:
    return {_camel_to_snake(k): v for k, v in d.items()}


class EntityPayload(BaseModel):
    entity_type: str
    hierarchy_level: int
    payload: dict[str, Any]

    @model_validator(mode='after')
    def convert_payload_keys(self) -> 'EntityPayload':
        if isinstance(self.payload, dict):
            self.payload = _convert_dict_keys(self.payload)
        return self

class SyncJobRequest(BaseModel):
    entities: list[EntityPayload]

class SyncJobResponse(BaseModel):
    job_id: UUID
    status: str
    message: str
    status_url: str
