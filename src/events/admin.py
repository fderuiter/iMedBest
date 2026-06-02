from django.contrib import admin

from .models import DeliveryAttempt, OutboundEvent, Subscription
from .tasks import process_delivery_attempt


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("name", "endpoint_url", "event_type", "is_active", "created_at")
    list_filter = ("is_active", "event_type")


@admin.register(OutboundEvent)
class OutboundEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "action", "status", "created_at")
    list_filter = ("event_type", "action", "status")
    search_fields = ("event_id",)


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ("event", "subscription", "status", "timestamp", "retry_count")
    list_filter = ("status", "subscription")
    search_fields = ("event__event_id",)
    actions = ["retry_failed"]

    def retry_failed(self, request, queryset):
        failed_attempts = list(queryset.filter(status="FAILED"))
        for attempt in failed_attempts:
            attempt.status = "PENDING"
            attempt.error_message = None
            attempt.save(update_fields=["status", "error_message"])
            process_delivery_attempt.delay(attempt.id)

        self.message_user(request, f"Marked {len(failed_attempts)} failed attempts as PENDING and queued for retry.")

    retry_failed.short_description = "Retry selected failed deliveries"
