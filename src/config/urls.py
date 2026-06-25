from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from clinical.views import DashboardView, RetriggerTimelineTaskView
from users.views import LoginView, LogoutView

from .api import api


def health_check(request):
    return HttpResponse("OK", status=200)


urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("oauth2/", include("django_auth_adfs.urls")),
    path("retrigger-timeline/", RetriggerTimelineTaskView.as_view(), name="retrigger_timeline"),
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    path("health", health_check, name="health"),
]
