from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import DeliveryAttempt, OutboundEvent, Subscription
from .serializers import get_hierarchical_batch
from .tasks import process_delivery_attempt


def create_event(action, instance):
    from django.db.models import Q

    from clinical.models import ClinicalEntity

    if not isinstance(instance, ClinicalEntity):
        return

    # FILTER: Block clinical data (PHI/PII) from reaching outbound events
    return

    model_name = instance.__class__.__name__

    try:
        batch_payload = get_hierarchical_batch(instance)
    except Exception as e:
        batch_payload = {"error": str(e)}

    study_ids = []
    site_ids = []
    if isinstance(batch_payload, list):
        for entity in batch_payload:
            if entity.get("type") == "Study":
                study_ids.append(entity.get("id"))
            elif entity.get("type") == "Site":
                site_ids.append(entity.get("id"))

    record_revision = None
    if model_name == "Record":
        record_revision = instance.revisions.order_by("-created_at").first()

    # Create Outbound Event
    event = OutboundEvent.objects.create(
        event_type=model_name,
        action=action,
        payload=batch_payload,
        record_revision=record_revision,
    )

    # Fan out to subscriptions
    subscriptions = Subscription.objects.filter(is_active=True).filter(
        Q(study_id__in=study_ids) | Q(site_id__in=site_ids)
    )
    for sub in subscriptions:
        if not sub.event_type or sub.event_type == model_name:
            attempt = DeliveryAttempt.objects.create(event=event, subscription=sub)
            transaction.on_commit(lambda a_id=attempt.id: process_delivery_attempt.delay(a_id))


@receiver(post_save)
def track_clinical_save(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if sender._meta.app_label != "clinical":
        return

    action = "CREATE" if created else "UPDATE"
    create_event(action, instance)


@receiver(post_delete)
def track_clinical_delete(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    if sender._meta.app_label != "clinical":
        return

    create_event("DELETE", instance)
