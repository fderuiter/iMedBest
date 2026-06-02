import os

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("imedbest")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@before_task_publish.connect
def inject_context_into_task(headers=None, **kwargs):
    if headers is None:
        return

    from audit.middleware import get_current_request
    request = get_current_request()

    if request:
        headers["__user_id"] = getattr(request.user, "pk", None) if hasattr(request, "user") and request.user else None

        ip = ""
        if hasattr(request, "META"):
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0]
            else:
                ip = request.META.get("REMOTE_ADDR", "")

        headers["__ip_address"] = ip
        headers["__user_agent"] = request.META.get("HTTP_USER_AGENT", "") if hasattr(request, "META") else ""


class MockRequest:
    def __init__(self, user_id, ip_address, user_agent):
        self.META = {"REMOTE_ADDR": ip_address, "HTTP_USER_AGENT": user_agent}
        if user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                self.user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                from django.contrib.auth.models import AnonymousUser

                self.user = AnonymousUser()
        else:
            from django.contrib.auth.models import AnonymousUser

            self.user = AnonymousUser()


_celery_task_tokens = {}


@task_prerun.connect
def setup_task_context(task_id, task, *args, **kwargs):
    from audit.middleware import _request_ctx_var
    request_headers = getattr(task.request, "headers", {}) or {}

    # fallback to task.request if headers are flat?
    if "__user_id" not in request_headers and hasattr(task.request, "__user_id"):
        user_id = getattr(task.request, "__user_id", None)
        ip_address = getattr(task.request, "__ip_address", "")
        user_agent = getattr(task.request, "__user_agent", "")
    else:
        user_id = request_headers.get("__user_id")
        ip_address = request_headers.get("__ip_address", "")
        user_agent = request_headers.get("__user_agent", "")

    mock_request = MockRequest(user_id, ip_address, user_agent)
    token = _request_ctx_var.set(mock_request)
    _celery_task_tokens[task_id] = token


@task_postrun.connect
def teardown_task_context(task_id, task, *args, **kwargs):
    from audit.middleware import _request_ctx_var
    token = _celery_task_tokens.pop(task_id, None)
    if token:
        _request_ctx_var.reset(token)
