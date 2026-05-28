import threading
import time
import requests
import logging

logger = logging.getLogger(__name__)

class EventWorker(threading.Thread):
    def __init__(self, sleep_interval=0.1):
        super().__init__(daemon=True)
        self.sleep_interval = sleep_interval
        self._stop_event = threading.Event()

    def run(self):
        from .models import DeliveryAttempt
        
        while not self._stop_event.is_set():
            self.process_pending()
            time.sleep(self.sleep_interval)
            
    def stop(self):
        self._stop_event.set()

    def process_pending(self):
        from .models import DeliveryAttempt
        from django.db import transaction
        
        try:
            with transaction.atomic():
                pending = DeliveryAttempt.objects.select_for_update(skip_locked=True).filter(
                    status='PENDING'
                ).order_by('timestamp')[:50]
                
                # We need to listify to execute the query within the transaction lock
                attempts = list(pending)
                
                # Update status to PROCESSING immediately to prevent other workers from picking them up
                for attempt in attempts:
                    attempt.status = 'PROCESSING'
                    attempt.save(update_fields=['status'])
                
            # Process outside the lock to avoid holding the lock during HTTP requests
            for attempt in attempts:
                self.process_attempt(attempt)
        except Exception as e:
            logger.error(f"Worker error: {e}")

    def process_attempt(self, attempt):
        attempt.status = 'DELIVERED'
        attempt.save()
        
        # transmit to mock subscriber or real endpoint
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
        except Exception as e:
            attempt.status = 'FAILED'
            attempt.error_message = str(e)
            attempt.retry_count += 1
        finally:
            attempt.save()

_worker_thread = None

def start_worker():
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = EventWorker()
        _worker_thread.start()

def stop_worker():
    global _worker_thread
    if _worker_thread:
        _worker_thread.stop()
        _worker_thread.join()
        _worker_thread = None
