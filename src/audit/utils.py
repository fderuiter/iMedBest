from django.db import models


class AdminRequest:
    def __init__(self, user):
        self.user = user
        self.META = {"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "Management Command"}
        self.path = "/management/command"


class AdminContext:
    def __init__(self, user=None):
        self.user = user
        self.token = None
        self.audit_token = None

    def __enter__(self):
        from django.contrib.auth import get_user_model

        from audit.middleware import _request_ctx_var
        from audit.signals import audit_override_bulk_flags

        User = get_user_model()
        if not self.user:
            self.user, _ = User.objects.get_or_create(
                username="admin_service",
                defaults={
                    "is_staff": True,
                    "is_superuser": True,
                    "email": "admin@service.local",
                    "first_name": "Administrative",
                    "last_name": "Service",
                },
            )

        request = AdminRequest(self.user)
        self.token = _request_ctx_var.set(request)
        self.audit_token = audit_override_bulk_flags.set(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from audit.middleware import _request_ctx_var
        from audit.signals import audit_override_bulk_flags

        _request_ctx_var.reset(self.token)
        audit_override_bulk_flags.reset(self.audit_token)


def extract_study_id(instance):
    if instance.__class__.__name__ == "Study":
        return getattr(instance, "id", None)

    # Short-circuit: check for local study_id first
    if hasattr(instance, "study_id") and instance.study_id:
        return instance.study_id

    if hasattr(instance, "get_subject") and callable(instance.get_subject):
        try:
            subject = instance.get_subject()
            if (
                subject
                and hasattr(subject, "site")
                and subject.site
                and hasattr(subject.site, "study_id")
                and subject.site.study_id
            ):
                return subject.site.study_id
        except Exception:  # noqa: S110
            pass

    # Common fields in clinical hierarchy - check FK ID before accessing related object
    for field in ["site", "subject", "form", "interval", "variable", "visit", "record"]:
        if hasattr(instance, field):
            # Check if the FK ID exists before materializing the parent
            fk_id = getattr(instance, f"{field}_id", None)
            if fk_id:
                parent = getattr(instance, field)
                if parent:
                    res = extract_study_id(parent)
                    if res:
                        return res

    # Generic fallback - check FK ID before accessing related object
    if hasattr(instance, "_meta"):
        for field in instance._meta.fields:
            if isinstance(field, models.ForeignKey) and field.name not in [
                "created_by",
                "updated_by",
                "user",
                "provider",
            ]:
                try:
                    # Check if the FK ID exists before materializing the parent
                    fk_id = getattr(instance, f"{field.name}_id", None)
                    if fk_id:
                        parent = getattr(instance, field.name)
                        if parent and parent != instance:
                            res = extract_study_id(parent)
                            if res:
                                return res
                except Exception:  # noqa: S110
                    pass
    return None


def sanitize_changes(instance, changes):
    if not changes or not hasattr(instance, "pii_fields"):
        return changes

    should_mask = False

    # 1. Mask if study has masking enabled
    if hasattr(instance, "get_study") and callable(instance.get_study):
        try:
            study = instance.get_study()
            if study and getattr(study, "pii_masking_enabled", False):
                should_mask = True
        except Exception:  # noqa: S110
            pass

    # 2. Mask if instance itself contains PHI (global clinical metadata)
    if getattr(instance, "contains_phi", False):
        should_mask = True

    if should_mask:
        for field in getattr(instance, "pii_fields", []):
            if field in changes:
                if changes[field].get("old") is not None and changes[field]["old"] != "":
                    changes[field]["old"] = "[REDACTED]"
                if changes[field].get("new") is not None and changes[field]["new"] != "":
                    changes[field]["new"] = "[REDACTED]"

    return changes
