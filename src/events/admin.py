from django.contrib import admin

from .models import DeliveryAttempt, OutboundEvent, Subscription


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
    list_display = ("event", "subscription", "status", "timestamp")
    list_filter = ("status", "subscription")
    search_fields = ("event__event_id",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
