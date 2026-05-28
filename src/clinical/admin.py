from django.contrib import admin

from .models import SyncJob, SyncTask


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'user', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__username')

@admin.register(SyncTask)
class SyncTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'entity_type', 'hierarchy_level', 'status', 'retry_count', 'created_at')
    list_filter = ('status', 'entity_type', 'hierarchy_level')
    search_fields = ('id', 'job__id', 'error_message')
