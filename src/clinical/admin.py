from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

from .models import SyncJob, SyncTask


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'user', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__username')
    
    def changelist_view(self, request, extra_context=None):
        yesterday = timezone.now() - timedelta(hours=24)
        recent_jobs = SyncJob.objects.filter(created_at__gte=yesterday)
        
        pending_count = recent_jobs.filter(status='PENDING').count()
        failed_count = recent_jobs.filter(status='FAILED').count()
        
        msg = f"Last 24 hours - Pending Jobs: {pending_count} | Failed Jobs: {failed_count}"
        messages.info(request, msg)
        
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(SyncTask)
class SyncTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'entity_type', 'hierarchy_level', 'status', 'retry_count', 'created_at')
    list_filter = ('status', 'entity_type', 'hierarchy_level')
    search_fields = ('id', 'job__id', 'error_message')
