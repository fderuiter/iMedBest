import logging

import requests
from celery import shared_task

from .models import DeliveryAttempt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_delivery_attempt(self, attempt_id):
    try:
        attempt = DeliveryAttempt.objects.get(id=attempt_id)
    except DeliveryAttempt.DoesNotExist:
        return

    if attempt.status != "PENDING":
        return

    attempt.status = "PROCESSING"
    attempt.save(update_fields=["status"])

    response_code = None

    try:
        payload = {
            "event_id": str(attempt.event.event_id),
            "event_type": attempt.event.event_type,
            "action": attempt.event.action,
            "batch": attempt.event.payload,
        }

        # Simple mock if endpoint is localhost/mock
        if "mock" in attempt.subscription.endpoint_url:
            response_code = 200
        else:
            response = requests.post(attempt.subscription.endpoint_url, json=payload, timeout=5)
            response_code = response.status_code
            response.raise_for_status()

        attempt.status = "DELIVERED"
        attempt.error_message = ""
        attempt.response_code = response_code
        attempt.save(update_fields=["status", "error_message", "response_code"])
    except Exception as e:
        if isinstance(e, requests.RequestException) and getattr(e, "response", None) is not None:
            response_code = e.response.status_code

        attempt.status = "FAILED"
        attempt.error_message = str(e)
        attempt.response_code = response_code
        attempt.save(update_fields=["status", "error_message", "response_code"])

        try:
            if self.request.retries < self.max_retries:
                new_attempt = DeliveryAttempt.objects.create(
                    event=attempt.event, subscription=attempt.subscription, status="PENDING"
                )
                raise self.retry(exc=e, countdown=2**self.request.retries, args=[new_attempt.id])
        except self.MaxRetriesExceededError:
            pass
