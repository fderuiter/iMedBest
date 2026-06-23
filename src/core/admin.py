from django.contrib import admin

from .models import Form


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Forms.
    """

    list_display = ("form_key", "form_name", "form_type", "disabled", "study")
    list_filter = ("disabled", "form_type", "study")
    search_fields = ("form_key", "form_name", "imednet_id")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "imednet_id",
        "form_key",
        "form_name",
        "form_type",
        "revision",
        "embedded_log",
        "enforce_ownership",
        "user_agreement",
        "subject_record_report",
        "unscheduled_visit",
        "other_forms",
        "epro_form",
        "allow_copy",
        "disabled",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study")
