from typing import List

from ninja import Query as NinjaQuery
from ninja import Router
from ninja.pagination import paginate

from config.pagination import SafeLimitOffsetPagination

from .filters import RecordFilter, SubjectFilter
from .models import Record, Subject
from .schemas import RecordOut, SubjectOut

router = Router(tags=["Core API"])


@router.get("/subjects", response=List[SubjectOut])
@paginate(SafeLimitOffsetPagination)
def list_subjects(request, filters: SubjectFilter = NinjaQuery(...)):
    qs = Subject.objects.select_related("study", "site").prefetch_related("keywords").order_by("id")
    qs = filters.filter(qs)
    return qs


@router.get("/records", response=List[RecordOut])
@paginate(SafeLimitOffsetPagination)
def list_records(request, filters: RecordFilter = NinjaQuery(...)):
    qs = (
        Record.objects.select_related("study", "subject", "site", "form", "interval", "visit")
        .prefetch_related("keywords")
        .order_by("id")
    )
    qs = filters.filter(qs)
    return qs
