import os
import threading
from collections import OrderedDict

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
        user_pk = getattr(request.user, "pk", None) if hasattr(request, "user") and request.user else None
        headers["audit_user_id"] = user_pk

        ip = ""
        if hasattr(request, "META"):
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR", "")

        headers["audit_ip_address"] = ip
        headers["audit_user_agent"] = request.META.get("HTTP_USER_AGENT", "") if hasattr(request, "META") else ""


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


_TASK_TOKEN_MAX = 2048
_celery_task_tokens: OrderedDict = OrderedDict()
_celery_task_tokens_lock = threading.Lock()


def _put_token(task_id, token):
    with _celery_task_tokens_lock:
        _celery_task_tokens[task_id] = token
        while len(_celery_task_tokens) > _TASK_TOKEN_MAX:
            _celery_task_tokens.popitem(last=False)


def _pop_token(task_id):
    with _celery_task_tokens_lock:
        return _celery_task_tokens.pop(task_id, None)


@task_prerun.connect
def setup_task_context(task_id, task, *args, **kwargs):
    from audit.middleware import _request_ctx_var
    request_headers = getattr(task.request, "headers", {}) or {}

    user_id = request_headers.get("audit_user_id")
    ip_address = request_headers.get("audit_ip_address", "")
    user_agent = request_headers.get("audit_user_agent", "")

    mock_request = MockRequest(user_id, ip_address, user_agent)
    token = _request_ctx_var.set(mock_request)
    _put_token(task_id, token)


@task_postrun.connect
def teardown_task_context(task_id, task, *args, **kwargs):
    from audit.middleware import _request_ctx_var
    token = _pop_token(task_id)
    if token:
        _request_ctx_var.reset(token)
