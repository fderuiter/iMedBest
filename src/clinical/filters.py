from datetime import date
from typing import Annotated

from ninja import Field, FilterLookup, FilterSchema


class SubjectFilter(FilterSchema):
    site_id: Annotated[int | None, FilterLookup(q="site_id")] = Field(None, alias="siteId")
    status: Annotated[str | None, FilterLookup(q="status")] = None
    dob_start: Annotated[date | None, FilterLookup(q="date_of_birth__gte")] = Field(None, alias="dobStart")
    dob_end: Annotated[date | None, FilterLookup(q="date_of_birth__lte")] = Field(None, alias="dobEnd")


class RecordFilter(FilterSchema):
    record_id: Annotated[str | None, FilterLookup(q="external_id")] = Field(None, alias="recordId")
    study_id: Annotated[int | None, FilterLookup(q="visit__subject__site__study_id")] = Field(None, alias="studyId")
