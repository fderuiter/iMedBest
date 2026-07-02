from datetime import date
from typing import Annotated, Optional

from ninja import Field, FilterLookup, FilterSchema


class SubjectFilter(FilterSchema):
    site_id: Annotated[Optional[int], FilterLookup(q="site_id")] = None
    status: Annotated[Optional[str], FilterLookup(q="subject_status")] = None
    dob_start: Annotated[Optional[date], FilterLookup(q="date_of_birth__gte")] = None
    dob_end: Annotated[Optional[date], FilterLookup(q="date_of_birth__lte")] = None


class RecordFilter(FilterSchema):
    record_id: Annotated[Optional[str], FilterLookup(q="imednet_id")] = None
    study_id: Annotated[Optional[int], FilterLookup(q="study_id")] = None
