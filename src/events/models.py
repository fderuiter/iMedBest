import uuid

from django.db import models


class Subscription(models.Model):
    name = models.CharField(max_length=255)
    endpoint_url = models.URLField(max_length=1000)
    event_type = models.CharField(
        max_length=255, blank=True, null=True, help_text="Filter by event type (e.g., 'Record'). Leave blank for all."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

    def __str__(self):
        return f"{self.name} - {self.endpoint_url}"


class OutboundEvent(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("DELIVERED", "Delivered"),
        ("FAILED", "Failed"),
    )

    event_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    event_type = models.CharField(max_length=255)  # Model name like 'Record'
    action = models.CharField(max_length=50)  # CREATE, UPDATE, DELETE
    payload = models.JSONField()  # The hierarchical batch data
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)

    # We might want to link it to specific subscriptions, or we just fan-out on generation.
    # To support independent subscriptions (Req 6), maybe we store DeliveryAttempt per subscription.


class DeliveryAttempt(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("DELIVERED", "Delivered"),
        ("FAILED", "Failed"),
    )
    event = models.ForeignKey(OutboundEvent, on_delete=models.CASCADE, related_name="deliveries")
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    timestamp = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True, null=True)
    response_code = models.IntegerField(null=True, blank=True)
