from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save, pre_save
from django.db.utils import OperationalError
from django.dispatch import receiver
from django.forms.models import model_to_dict

from .middleware import get_current_request
from .tasks import create_audit_log_task
from .utils import extract_study_id

EXCLUDED_MODELS = ["AuditLog", "Session", "LogEntry", "ContentType", "Permission", "Group", "Revision", "Migration"]


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def create_audit_log(action, instance, changes=None):
    model_name = instance.__class__.__name__
    if model_name in EXCLUDED_MODELS:
        return

    request = get_current_request()
    user = getattr(request, "user", None) if request else None
    if user and not user.is_authenticated:
        user = None

    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT") if request else None

    study_id = extract_study_id(instance)

    # Redact tagged PII fields for masked studies
    if changes and hasattr(instance, "pii_fields") and hasattr(instance, "get_study"):
        study = instance.get_study()
        if study and getattr(study, "pii_masking_enabled", False):
            for field in instance.pii_fields:
                if field in changes:
                    if changes[field].get("old") is not None and changes[field]["old"] != "":
                        changes[field]["old"] = "[REDACTED]"
                    if changes[field].get("new") is not None and changes[field]["new"] != "":
                        changes[field]["new"] = "[REDACTED]"

    create_audit_log_task.delay(
        action=action,
        model_name=model_name,
        object_id=str(instance.pk),
        changes=changes,
        user_id=user.pk if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        study_id=study_id,
    )


def safe_model_to_dict(instance):
    d = model_to_dict(instance)
    for k, v in d.items():
        if v.__class__.__name__ == "UUID":
            d[k] = str(v)
        elif hasattr(v, "pk"):
            d[k] = str(v.pk)
        elif hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@receiver(pre_save)
def track_changes(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    if sender.__name__ in EXCLUDED_MODELS:
        return
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_data = safe_model_to_dict(old_instance)
        except (sender.DoesNotExist, OperationalError):
            instance._old_data = {}
    else:
        instance._old_data = {}


@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if sender.__name__ in EXCLUDED_MODELS:
        return
    action = "CREATE" if created else "UPDATE"

    changes = {}
    if not created and hasattr(instance, "_old_data"):
        new_data = safe_model_to_dict(instance)
        for key, value in new_data.items():
            old_value = instance._old_data.get(key)
            if str(old_value) != str(value):
                changes[key] = {"old": str(old_value), "new": str(value)}

    create_audit_log(action, instance, changes if changes else None)


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    create_audit_log("DELETE", instance)


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT") if request else None
    create_audit_log_task.delay(
        action="LOGIN",
        model_name="",
        object_id="",
        changes=None,
        user_id=user.pk if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT") if request else None
    create_audit_log_task.delay(
        action="LOGOUT",
        model_name="",
        object_id="",
        changes=None,
        user_id=user.pk if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
