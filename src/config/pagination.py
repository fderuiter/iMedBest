from typing import Any, List, Optional

from django.db.models import QuerySet
from ninja import Field, Schema
from ninja.pagination import LimitOffsetPagination
from ninja.types import DictStrAny


class SafeLimitOffsetPagination(LimitOffsetPagination):
    class Input(Schema):
        limit: Optional[int] = Field(25, ge=1)
        offset: Optional[int] = Field(0, ge=0)

    def __init__(self, max_limit: int = 100, **kwargs: Any) -> None:
        self.max_limit = max_limit
        super().__init__(**kwargs)

    def paginate_queryset(self, queryset: Any, pagination: Input, **params: DictStrAny) -> Any:
        offset = pagination.offset or 0
        limit = pagination.limit or 25

        if limit > self.max_limit:
            limit = self.max_limit

        if isinstance(queryset, list):
            count = len(queryset)
            items = queryset[offset : offset + limit]
        else:
            count = queryset.count()
            items = queryset[offset : offset + limit]

        return {
            "items": items,
            "count": count,
        }
