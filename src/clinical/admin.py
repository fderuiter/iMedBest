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

from django.contrib.admin import SimpleListFilter

class DeletedFilter(SimpleListFilter):
    title = 'Is Deleted'
    parameter_name = 'is_deleted'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_deleted=True)
        if self.value() == 'no':
            return queryset.filter(is_deleted=False)
        return queryset

from .models import Study, Site, Subject

class SoftDeleteAdmin(admin.ModelAdmin):
    list_display = ('external_id', 'is_deleted', 'deleted_at', 'created_at')
    list_filter = (DeletedFilter,)
    search_fields = ('external_id',)
    
    def get_queryset(self, request):
        return self.model.all_objects.all()

@admin.register(Study)
class StudyAdmin(SoftDeleteAdmin):
    pass

@admin.register(Site)
class SiteAdmin(SoftDeleteAdmin):
    pass

@admin.register(Subject)
class SubjectAdmin(SoftDeleteAdmin):
    pass


from .models import Provider

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'api_endpoint', 'auth_protocol')
    search_fields = ('name', 'api_endpoint')
    list_filter = ('auth_protocol',)
