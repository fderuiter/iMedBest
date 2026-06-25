import logging

import ninja.operation
import ninja.orm
import ninja.schema
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404
from ninja import NinjaAPI
from ninja.errors import ValidationError as NinjaValidationError
from pydantic.alias_generators import to_camel

logger = logging.getLogger("django.request")

# 1. Initialize NinjaAPI with metadata and conditional docs
api = NinjaAPI(
    title="iMedBest Enterprise API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
)

# Explicitly disable Redoc if not in DEBUG mode
if not settings.DEBUG:
    api.redoc_url = None

# 2. Centralize camelCase and alias generator configurations
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

# 3. Implement standardized global exception handlers


@api.exception_handler(ObjectDoesNotExist)
@api.exception_handler(Http404)
def handle_not_found(request, exc):
    return api.create_response(
        request,
        {
            "success": False,
            "error": "ResourceNotFound",
            "message": "The requested resource was not found.",
        },
        status=404,
    )


@api.exception_handler(NinjaValidationError)
@api.exception_handler(DjangoValidationError)
def handle_validation_error(request, exc):
    if isinstance(exc, NinjaValidationError):
        details = exc.errors
    else:
        # Django ValidationError
        details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages

    return api.create_response(
        request,
        {
            "success": False,
            "error": "ValidationError",
            "message": "Invalid request parameters.",
            "details": details,
        },
        status=422,
    )


@api.exception_handler(IntegrityError)
def handle_integrity_error(request, exc):
    return api.create_response(
        request,
        {
            "success": False,
            "error": "Conflict",
            "message": "A database integrity conflict occurred.",
        },
        status=409,
    )


@api.exception_handler(OperationalError)
def handle_operational_error(request, exc):
    logger.error("Database Operational Error: %s", exc, exc_info=True)
    return api.create_response(
        request,
        {
            "success": False,
            "error": "ServiceUnavailable",
            "message": "Database service is temporarily unavailable.",
        },
        status=503,
    )


@api.exception_handler(Exception)
def handle_generic_exception(request, exc):
    logger.error("Internal Server Error: %s", exc, exc_info=True)
    return api.create_response(
        request,
        {
            "success": False,
            "error": "InternalServerError",
            "message": "An unexpected internal error occurred.",
        },
        status=500,
    )


# 4. Implement dynamic loading and mounting of domain routers
api.add_router("/clinical/", "clinical.api.router", tags=["Clinical"])
# Restore spec-compliant mount point
api.add_router(
    "/v1/edc/studies/{studyKey}/",
    "clinical.api.router",
    tags=["Clinical Spec-Compliant"],
    url_name_prefix="spec",
)
api.add_router("/users/", "users.api.router", tags=["Users"])
api.add_router("/audit/", "audit.api.router", tags=["Audit"])
