import structlog
from django.http import JsonResponse
from rest_framework import exceptions

logger = structlog.get_logger(__name__)


class JWTRuntimeErrorHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (exceptions.AuthenticationFailed, exceptions.NotAuthenticated) as e:
            # Securely log authentication failure
            logger.warning(
                "JWT authentication failure",
                error_type=e.__class__.__name__,
                detail=str(e),
                path=request.path,
                ip_address=self.get_client_ip(request),
            )
            return JsonResponse({"detail": str(e)}, status=401)
        except Exception as e:
            # Re-raise other exceptions for normal handling
            raise e

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        return x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")
