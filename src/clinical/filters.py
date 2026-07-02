from datetime import date
from typing import Annotated, Optional

from ninja import Field, FilterLookup, FilterSchema


class SubjectFilter(FilterSchema):
    site_id: Annotated[Optional[int], FilterLookup(q="site_id")] = None
    status: Annotated[Optional[str], FilterLookup(q="status")] = None
    dob_start: Annotated[Optional[date], FilterLookup(q="date_of_birth__gte")] = None
    dob_end: Annotated[Optional[date], FilterLookup(q="date_of_birth__lte")] = None


class RecordFilter(FilterSchema):
    record_id: Annotated[Optional[str], FilterLookup(q="external_id")] = None
    study_id: Annotated[Optional[int], FilterLookup(q="visit__subject__site__study_id")] = None
