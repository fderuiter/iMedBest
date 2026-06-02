from django.db import models


def extract_study_id(instance):
    if instance.__class__.__name__ == "Study":
        return getattr(instance, "id", None)

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

    # Common fields in clinical hierarchy
    for field in ["site", "subject", "form", "interval", "variable", "visit", "record"]:
        if hasattr(instance, field):
            parent = getattr(instance, field)
            if parent:
                res = extract_study_id(parent)
                if res:
                    return res

    # Generic fallback
    if hasattr(instance, "_meta"):
        for field in instance._meta.fields:
            if isinstance(field, models.ForeignKey) and field.name not in [
                "created_by",
                "updated_by",
                "user",
                "provider",
            ]:
                try:
                    parent = getattr(instance, field.name)
                    if parent and parent != instance:
                        res = extract_study_id(parent)
                        if res:
                            return res
                except Exception:  # noqa: S110
                    pass

    return None
