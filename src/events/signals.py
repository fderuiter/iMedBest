from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from .models import OutboundEvent, DeliveryAttempt, Subscription
from .serializers import get_hierarchical_batch

def create_event(action, instance):
    from clinical.models import ClinicalEntity
    
    if not isinstance(instance, ClinicalEntity):
        return

    model_name = instance.__class__.__name__
    
    try:
        batch_payload = get_hierarchical_batch(instance)
    except Exception as e:
        batch_payload = {"error": str(e)}

    # Create Outbound Event
    event = OutboundEvent.objects.create(
        event_type=model_name,
        action=action,
        payload=batch_payload
    )

    # Fan out to subscriptions
    subscriptions = Subscription.objects.filter(is_active=True)
    for sub in subscriptions:
        if not sub.event_type or sub.event_type == model_name:
            DeliveryAttempt.objects.create(
                event=event,
                subscription=sub
            )

@receiver(post_save)
def track_clinical_save(sender, instance, created, **kwargs):
    if kwargs.get('raw'): return
    if sender._meta.app_label != 'clinical':
        return
        
    action = 'CREATE' if created else 'UPDATE'
    create_event(action, instance)

@receiver(post_delete)
def track_clinical_delete(sender, instance, **kwargs):
    if kwargs.get('raw'): return
    if sender._meta.app_label != 'clinical':
        return
        
    create_event('DELETE', instance)
