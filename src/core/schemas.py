from datetime import datetime
from typing import Any

from ninja import Field, ModelSchema, Schema
from pydantic import AliasChoices, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from .models import (
    Coding,
    Form,
    Interval,
    Job,
    Query,
    QueryComment,
    Record,
    RecordKeyword,
    RecordRevision,
    Subject,
    SubjectKeyword,
    User,
    UserRole,
    Variable,
    Visit,
)


class ResilientDateSchema(Schema):
    @field_validator("*", mode="before")
    @classmethod
    def parse_imednet_date(cls, v: Any) -> Any:
        if isinstance(v, list) and len(v) >= 3:
            try:
                from datetime import UTC

                args = v[:6]
                return datetime(*args, tzinfo=UTC)
            except (ValueError, TypeError):
                return v
        return v


class SyncedResourceSchema(ResilientDateSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    imednet_id: str
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime = Field(validation_alias=AliasChoices("last_synced_at", "updated_at"))


# --- User & Roles ---


class UserRoleOut(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = UserRole
        fields = ["id", "role_name", "start_date", "end_date"]


class UserRoleIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = UserRole
        fields = ["role_name", "start_date", "end_date"]


class UserOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    roles: list[UserRoleOut] = []

    class Meta:
        model = User
        fields = [
            "imednet_id",
            "login",
            "first_name",
            "last_name",
            "email",
            "user_active_in_study",
            "created_at",
            "updated_at",
        ]


class UserIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "user_active_in_study"]


# --- Forms ---


class FormOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Form
        fields = [
            "imednet_id",
            "form_key",
            "form_name",
            "form_type",
            "revision",
            "embedded_log",
            "enforce_ownership",
            "user_agreement",
            "subject_record_report",
            "unscheduled_visit",
            "other_forms",
            "epro_form",
            "allow_copy",
            "disabled",
            "created_at",
            "updated_at",
        ]


class FormIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Form
        fields = [
            "form_name",
            "form_type",
            "revision",
            "embedded_log",
            "enforce_ownership",
            "user_agreement",
            "subject_record_report",
            "unscheduled_visit",
            "other_forms",
            "epro_form",
            "allow_copy",
            "disabled",
        ]


# --- Intervals ---


class IntervalOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Interval
        fields = [
            "imednet_id",
            "interval_name",
            "interval_description",
            "interval_sequence",
            "interval_group_id",
            "interval_group_name",
            "timeline",
            "defined_using_interval",
            "window_calculation_form",
            "window_calculation_date",
            "actual_date_form",
            "actual_date",
            "due_date_will_be_in",
            "negative_slack",
            "positive_slack",
            "epro_grace_period",
            "disabled",
            "created_at",
            "updated_at",
        ]


class IntervalIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Interval
        fields = [
            "interval_name",
            "interval_description",
            "interval_sequence",
            "interval_group_id",
            "interval_group_name",
            "timeline",
            "defined_using_interval",
            "window_calculation_form",
            "window_calculation_date",
            "actual_date_form",
            "actual_date",
            "due_date_will_be_in",
            "negative_slack",
            "positive_slack",
            "epro_grace_period",
            "disabled",
        ]


# --- Variables ---


class VariableOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Variable
        fields = [
            "imednet_id",
            "variable_type",
            "variable_name",
            "sequence",
            "revision",
            "disabled",
            "variable_oid",
            "deleted",
            "label",
            "blinded",
            "form_key_raw",
            "created_at",
            "updated_at",
        ]


class VariableIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Variable
        fields = [
            "variable_type",
            "variable_name",
            "sequence",
            "revision",
            "disabled",
            "variable_oid",
            "deleted",
            "label",
            "blinded",
            "form_key_raw",
        ]


# --- Subjects ---


class SubjectKeywordOut(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = SubjectKeyword
        fields = ["id", "keyword"]


class SubjectOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    keywords: list[SubjectKeywordOut] = []

    class Meta:
        model = Subject
        fields = [
            "imednet_id",
            "subject_oid",
            "subject_key",
            "subject_status",
            "enrollment_start_date",
            "deleted",
            "site_name_raw",
            "created_at",
            "updated_at",
        ]


class SubjectIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Subject
        fields = ["subject_status", "enrollment_start_date", "deleted", "site_name_raw"]


# --- Visits ---


class VisitOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Visit
        fields = [
            "imednet_id",
            "interval_name_raw",
            "subject_key_raw",
            "start_date",
            "end_date",
            "due_date",
            "visit_date",
            "visit_date_form",
            "deleted",
            "visit_date_question",
            "created_at",
            "updated_at",
        ]


class VisitIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Visit
        fields = [
            "interval_name_raw",
            "subject_key_raw",
            "start_date",
            "end_date",
            "due_date",
            "visit_date",
            "visit_date_form",
            "deleted",
            "visit_date_question",
        ]


# --- Records ---


class RecordKeywordOut(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = RecordKeyword
        fields = ["id", "keyword"]


class RecordOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    keywords: list[RecordKeywordOut] = []

    class Meta:
        model = Record
        fields = [
            "imednet_id",
            "record_oid",
            "record_type",
            "record_status",
            "deleted",
            "imednet_subject_id",
            "subject_oid",
            "subject_key",
            "imednet_visit_id",
            "parent_record_id",
            "record_data",
            "created_at",
            "updated_at",
        ]


class RecordIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Record
        fields = [
            "record_type",
            "record_status",
            "deleted",
            "imednet_subject_id",
            "subject_oid",
            "subject_key",
            "imednet_visit_id",
            "parent_record_id",
            "record_data",
        ]


# --- Coding ---


class CodingOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Coding
        fields = [
            "imednet_id",
            "site_name",
            "site_id",
            "imednet_subject_id",
            "revision",
            "imednet_record_id",
            "value",
            "code",
            "reason",
            "dictionary_name",
            "dictionary_version",
            "date_coded",
            "subject_key_raw",
            "variable_raw",
            "coded_by_raw",
            "created_at",
            "updated_at",
        ]


class CodingIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Coding
        fields = [
            "site_name",
            "site_id",
            "imednet_subject_id",
            "revision",
            "imednet_record_id",
            "value",
            "code",
            "reason",
            "dictionary_name",
            "dictionary_version",
            "date_coded",
            "subject_key_raw",
            "variable_raw",
            "coded_by_raw",
        ]


# --- Query ---


class QueryCommentOut(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = QueryComment
        fields = ["id", "comment", "user_raw", "date_created"]


class QueryOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    comments: list[QueryCommentOut] = []

    class Meta:
        model = Query
        fields = [
            "imednet_id",
            "imednet_subject_id",
            "subject_oid",
            "annotation_type",
            "query_type",
            "description",
            "imednet_record_id",
            "variable_raw",
            "subject_key",
            "created_at",
            "updated_at",
        ]


class QueryIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Query
        fields = [
            "annotation_type",
            "query_type",
            "description",
            "imednet_record_id",
            "variable_raw",
            "subject_key",
        ]


# --- Job ---


class JobOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = Job
        fields = [
            "imednet_id",
            "batch_id",
            "state",
            "date_created",
            "date_started",
            "date_finished",
            "created_at",
            "updated_at",
        ]


class JobIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = Job
        fields = ["batch_id", "state", "date_created", "date_started", "date_finished"]


# --- Record Revision ---


class RecordRevisionOut(ModelSchema, SyncedResourceSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = RecordRevision
        fields = [
            "imednet_id",
            "imednet_record_id",
            "record_oid",
            "record_revision",
            "data_revision",
            "record_status",
            "imednet_subject_id",
            "subject_oid",
            "subject_key",
            "site_id",
            "form_key",
            "interval_id",
            "role",
            "user_raw",
            "reason_for_change",
            "deleted",
            "created_at",
            "updated_at",
        ]


class RecordRevisionIn(ModelSchema, ResilientDateSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = RecordRevision
        fields = [
            "record_revision",
            "data_revision",
            "record_status",
            "imednet_subject_id",
            "subject_oid",
            "subject_key",
            "site_id",
            "form_key",
            "interval_id",
            "role",
            "user_raw",
            "reason_for_change",
            "deleted",
        ]
