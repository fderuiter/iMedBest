import ninja.operation
import ninja.orm
import ninja.schema
from django.contrib import admin
from django.urls import path
from pydantic.alias_generators import to_camel

ninja.schema.Schema.model_config["alias_generator"] = to_camel
ninja.schema.Schema.model_config["populate_by_name"] = True
ninja.orm.ModelSchema.model_config["alias_generator"] = to_camel
ninja.orm.ModelSchema.model_config["populate_by_name"] = True

original_operation_init = ninja.operation.Operation.__init__


def custom_operation_init(self, *args, **kwargs):
    if kwargs.get("by_alias") is None:
        kwargs["by_alias"] = True
    original_operation_init(self, *args, **kwargs)


ninja.operation.Operation.__init__ = custom_operation_init

from django.http import HttpResponse
from ninja import NinjaAPI

from audit.api import router as audit_router
from hub.api import router as hub_router
from hub.views import DashboardView
from users.api import router as users_router


def health_check(request):
    return HttpResponse("OK", status=200)


api = NinjaAPI()
api.add_router("/users/", users_router)
api.add_router("/audit/", audit_router)
api.add_router("/hub/", hub_router)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("health", health_check, name="health"),
]
