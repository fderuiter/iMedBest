import re
from datetime import datetime
from typing import Any
from uuid import UUID

from ninja import ModelSchema
from ninja import Schema as BaseModel
from pydantic import AliasChoices, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from .models import (
    BufferedOrphan,
    Coding,
    ExportJob,
    Form,
    Interval,
    Provider,
    Query,
    Record,
    RecordRevision,
    Site,
    Study,
    Subject,
    SyncJob,
    SyncTask,
    ValidationResult,
    ValidationRule,
    Variable,
    Visit,
)


def _camel_to_snake(name: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _convert_dict_keys(d: dict[str, Any]) -> dict[str, Any]:
    return {_camel_to_snake(k): v for k, v in d.items()}


class ClinicalResourceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    external_id: str
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))


class EntityPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    entity_type: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def convert_payload_keys(self) -> "EntityPayload":
        if isinstance(self.payload, dict):
            self.payload = _convert_dict_keys(self.payload)
        return self


class SyncJobRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    entities: list[EntityPayload]


class SyncJobResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    job_id: UUID
    status: str
    message: str
    status_url: str


# --- Provider ---


class ProviderOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Provider
        fields = [
            "id",
            "name",
            "api_endpoint",
            "auth_protocol",
            "auth_credentials",
            "hierarchy_mapping",
            "schema_mapping",
        ]


class ProviderIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Provider
        fields = ["name", "api_endpoint", "auth_protocol", "auth_credentials", "hierarchy_mapping", "schema_mapping"]


# --- Study ---


class StudyOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Study
        fields = ["external_id", "name", "pii_masking_enabled", "created_at", "updated_at"]


class StudyIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Study
        fields = ["name", "pii_masking_enabled"]


# --- Site ---


class SiteOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Site
        fields = ["external_id", "name", "created_at", "updated_at"]


class SiteIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Site
        fields = ["name"]


# --- Subject ---


class SubjectOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))
    site: SiteOut

    class Meta:
        model = Subject
        fields = ["external_id", "name", "contains_phi", "created_at", "updated_at"]


class SubjectIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Subject
        fields = ["name", "contains_phi"]


# --- Form ---


class FormOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Form
        fields = ["external_id", "name", "created_at", "updated_at"]


class FormIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Form
        fields = ["name"]


# --- Interval ---


class IntervalOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Interval
        fields = ["external_id", "name", "created_at", "updated_at"]


class IntervalIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Interval
        fields = ["name"]


# --- Variable ---


class VariableOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Variable
        fields = ["external_id", "name", "created_at", "updated_at"]


class VariableIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Variable
        fields = ["name"]


# --- Visit ---


class VisitOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))
    subject: SubjectOut
    interval: IntervalOut

    class Meta:
        model = Visit
        fields = ["external_id", "clinical_timestamp", "created_at", "updated_at"]


class VisitIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Visit
        fields = ["clinical_timestamp"]


# --- Record ---


class RecordOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Record
        fields = ["external_id", "value", "contains_phi", "clinical_timestamp", "created_at", "updated_at"]


class RecordIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Record
        fields = ["value", "contains_phi", "clinical_timestamp"]


# --- Coding ---


class CodingOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Coding
        fields = ["external_id", "code", "created_at", "updated_at"]


class CodingIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Coding
        fields = ["code"]


# --- Query ---


class QueryOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = Query
        fields = [
            "external_id",
            "text",
            "status",
            "previous_status",
            "sync_status",
            "last_sync_error",
            "created_at",
            "updated_at",
        ]


class QueryIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Query
        fields = ["text", "status", "previous_status", "sync_status", "last_sync_error"]


# --- Record Revision ---


class RecordRevisionOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))

    class Meta:
        model = RecordRevision
        fields = ["external_id", "value", "created_at", "updated_at"]


class RecordRevisionIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = RecordRevision
        fields = ["value"]


# --- Buffered Orphan ---


class BufferedOrphanOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = BufferedOrphan
        fields = ["id", "entity_type", "missing_parent_id", "payload", "created_at", "updated_at", "contains_phi"]


class BufferedOrphanIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = BufferedOrphan
        fields = ["entity_type", "missing_parent_id", "payload", "contains_phi"]


# --- Sync Job ---


class SyncJobOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = SyncJob
        fields = ["id", "status", "error_message", "file_path", "contains_phi", "created_at", "updated_at"]


class SyncJobIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = SyncJob
        fields = ["status", "error_message", "file_path", "contains_phi"]


# --- Sync Task ---


class SyncTaskOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = SyncTask
        fields = ["id", "entity_type", "payload", "status", "error_message", "retry_count", "created_at", "updated_at"]


class SyncTaskIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = SyncTask
        fields = ["entity_type", "payload", "status", "error_message", "retry_count"]


# --- Export Job ---


class ExportJobOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = ExportJob
        fields = ["id", "status", "file_path", "contains_phi", "created_at", "completed_at", "error_message"]


class ExportJobIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = ExportJob
        fields = ["status", "file_path", "contains_phi", "completed_at", "error_message"]


# --- Validation Rule ---


class ValidationRuleOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = ValidationRule
        fields = ["id", "name", "description", "rule_dsl", "is_active", "version", "created_at", "updated_at"]


class ValidationRuleIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = ValidationRule
        fields = ["name", "description", "rule_dsl", "is_active", "version"]


# --- Validation Result ---


class ValidationResultOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = ValidationResult
        fields = ["id", "passed", "error_message", "created_at"]


class ValidationResultIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = ValidationResult
        fields = ["passed", "error_message"]
