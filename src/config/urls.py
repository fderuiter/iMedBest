from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from audit.api import router as audit_router
from clinical.api import router as clinical_router
from clinical.views import DashboardView, RetriggerTimelineTaskView
from users.api import router as users_router

api = NinjaAPI()
api.add_router("/clinical/", clinical_router, tags=["legacy"], url_name_prefix="legacy")
api.add_router("/v1/edc/studies/{studyKey}/", clinical_router, tags=["spec-compliant"], url_name_prefix="spec")
api.add_router("/users/", users_router)
api.add_router("/audit/", audit_router)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("retrigger-timeline/", RetriggerTimelineTaskView.as_view(), name="retrigger_timeline"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
