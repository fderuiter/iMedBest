from django.contrib import admin
from .models import Provider

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'auth_type', 'api_endpoint', 'created_at', 'updated_at')
    search_fields = ('name', 'api_endpoint')
    list_filter = ('auth_type',)
