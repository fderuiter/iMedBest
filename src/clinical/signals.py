import uuid
from datetime import UTC, datetime

from django.core import serializers
from django.db.models.deletion import Collector
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from audit.middleware import get_current_request
from audit.models import AuditLog
from clinical.storage import get_storage_adapter

from .models import ClinicalEntity


def get_all_subclasses(cls):
    subclasses = set(cls.__subclasses__())
    for s in cls.__subclasses__():
        subclasses.update(get_all_subclasses(s))
    return subclasses


clinical_models = get_all_subclasses(ClinicalEntity)


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def archive_instance_and_descendants(instance):
    collector = Collector(using=instance._state.db)
    collector.collect([instance])

    objects_to_serialize = []
    for model, instances in collector.data.items():
        if issubclass(model, ClinicalEntity):
            objects_to_serialize.extend(instances)

    data_str = serializers.serialize("json", objects_to_serialize)

    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    rand_id = uuid.uuid4().hex[:8]
    filename = f"archive_{instance.__class__.__name__}_{instance.external_id}_{timestamp}_{rand_id}.json"

    adapter = get_storage_adapter()
    contains_phi = any(getattr(obj, "contains_phi", False) for obj in objects_to_serialize)
    return adapter.save(filename, data_str, namespace="archives", contains_phi=contains_phi)


@receiver(pre_delete)
def handle_clinical_entity_delete(sender, instance, **kwargs):
    if sender not in clinical_models:
        return

    try:
        filepath = archive_instance_and_descendants(instance)

        request = get_current_request()
        user = getattr(request, "user", None) if request else None
        if user and not user.is_authenticated:
            user = None

        ip_address = get_client_ip(request) if request else None
        user_agent = request.META.get("HTTP_USER_AGENT") if request else None

        AuditLog.objects.create(
            action="ARCHIVE",
            model_name=sender.__name__,
            object_id=str(instance.external_id),
            changes={"archive_file": filepath},
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        raise
