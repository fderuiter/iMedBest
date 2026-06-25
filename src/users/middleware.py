import jwt
from core.logging import get_logger
from django.http import JsonResponse
from django_auth_adfs.config import ConfigLoadError

logger = get_logger(__name__)


class JWTRuntimeErrorHandlerMiddleware:
    """
    Middleware to catch and securely log JWT authentication failures.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (jwt.PyJWTError, ConfigLoadError) as e:
            logger.error("jwt_authentication_failed", error=str(e), path=request.path)
            return JsonResponse({"error": "Authentication failed"}, status=401)
