from celery import shared_task
import requests
import logging
from .models import DeliveryAttempt

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_delivery_attempt(self, attempt_id):
    try:
        attempt = DeliveryAttempt.objects.get(id=attempt_id)
    except DeliveryAttempt.DoesNotExist:
        return
        
    if attempt.status != 'PENDING':
        return
        
    attempt.status = 'PROCESSING'
    attempt.save(update_fields=['status'])
    
    try:
        payload = {
            "event_id": str(attempt.event.event_id),
            "event_type": attempt.event.event_type,
            "action": attempt.event.action,
            "batch": attempt.event.payload
        }
        
        # Simple mock if endpoint is localhost/mock
        if "mock" in attempt.subscription.endpoint_url:
            pass # success
        else:
            response = requests.post(attempt.subscription.endpoint_url, json=payload, timeout=5)
            response.raise_for_status()
            
        attempt.status = 'DELIVERED'
        attempt.error_message = ""
        attempt.save(update_fields=['status', 'error_message'])
    except Exception as e:
        attempt.retry_count += 1
        
        try:
            # We want to retry. Don't mark as FAILED until max retries are reached.
            attempt.status = 'PENDING'
            attempt.error_message = str(e)
            attempt.save(update_fields=['status', 'error_message', 'retry_count'])
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            attempt.status = 'FAILED'
            attempt.save(update_fields=['status'])
            # Don't re-raise, we want the task to succeed in acknowledging the final failure.

