import threading

from audit.tasks import create_audit_log_task


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


_thread_locals = threading.local()


def get_current_request():
    return getattr(_thread_locals, "request", None)


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)

        if request.path.startswith("/api/clinical"):
            ip_address = get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT")

            if response.status_code == 401:
                create_audit_log_task.delay(
                    action="UNAUTH",
                    model_name="ClinicalAPI",
                    object_id=request.path,
                    changes={"error": "Unauthorized access attempt"},
                    user_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            elif request.method == "GET" and response.status_code == 200:
                user = getattr(request, "user", None)
                if user and user.is_authenticated:
                    create_audit_log_task.delay(
                        action="SECURITY",  # using SECURITY or another valid choice like UPDATE/CREATE
                        model_name="ClinicalAPI_Read",
                        object_id=request.path,
                        changes={"method": "GET", "status": 200},
                        user_id=user.pk,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )

        _thread_locals.request = None
        return response
