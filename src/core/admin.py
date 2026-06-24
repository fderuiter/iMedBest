from django.contrib import admin

from .models import (
    Coding,
    Form,
    Interval,
    Job,
    Query,
    QueryComment,
    Record,
    RecordKeyword,
    RecordRevision,
    Subject,
    SubjectKeyword,
    User,
    UserRole,
    Variable,
    Visit,
)


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    readonly_fields = ("role_name", "start_date", "end_date")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Users.
    """

    list_display = ("login", "email", "user_active_in_study", "study")
    list_filter = ("user_active_in_study", "study")
    search_fields = ("login", "email", "first_name", "last_name", "imednet_id")
    inlines = [UserRoleInline]

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "imednet_id",
        "login",
        "first_name",
        "last_name",
        "email",
        "user_active_in_study",
        "study",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related and prefetch_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study").prefetch_related("roles")


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


@admin.register(RecordRevision)
class RecordRevisionAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet RecordRevisions.
    """

    list_display = ("record_revision", "record_status", "user_profile", "reason_for_change", "study")
    list_filter = ("record_status", "study", "deleted")
    search_fields = ("imednet_id", "record_oid", "subject_key", "form_key")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "subject",
        "record",
        "user_profile",
        "imednet_id",
        "imednet_record_id",
        "record_oid",
        "record_revision",
        "data_revision",
        "record_status",
        "imednet_subject_id",
        "subject_oid",
        "subject_key",
        "site_id",
        "form_key",
        "interval_id",
        "role",
        "user_raw",
        "reason_for_change",
        "deleted",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study", "subject", "record", "user_profile")


@admin.register(Interval)
class IntervalAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Intervals.
    """

    list_display = ("interval_name", "interval_sequence", "disabled", "study")
    list_filter = ("disabled", "study")
    search_fields = ("interval_name", "imednet_id", "interval_group_name")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "imednet_id",
        "interval_name",
        "interval_description",
        "interval_sequence",
        "interval_group_id",
        "interval_group_name",
        "timeline",
        "defined_using_interval",
        "window_calculation_form",
        "window_calculation_date",
        "actual_date_form",
        "actual_date",
        "due_date_will_be_in",
        "negative_slack",
        "positive_slack",
        "epro_grace_period",
        "disabled",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related and prefetch_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study").prefetch_related("forms")


@admin.register(Variable)
class VariableAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Variables.
    """

    list_display = ("variable_oid", "variable_name", "variable_type", "deleted", "study")
    list_filter = ("deleted", "variable_type", "study")
    search_fields = ("variable_oid", "variable_name", "imednet_id")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "form",
        "form_key_raw",
        "imednet_id",
        "variable_type",
        "variable_name",
        "sequence",
        "revision",
        "disabled",
        "variable_oid",
        "deleted",
        "label",
        "blinded",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study", "form")


class SubjectKeywordInline(admin.TabularInline):
    model = SubjectKeyword
    extra = 0
    readonly_fields = ("keyword",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Subjects.
    """

    list_display = ("subject_key", "subject_status", "deleted", "study", "site")
    list_filter = ("subject_status", "deleted", "study")
    search_fields = ("subject_key", "imednet_id", "subject_oid")
    inlines = [SubjectKeywordInline]

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "site",
        "site_name_raw",
        "imednet_id",
        "subject_oid",
        "subject_key",
        "subject_status",
        "enrollment_start_date",
        "deleted",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related and prefetch_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study", "site").prefetch_related("keywords")


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Visits.
    """

    list_display = ("imednet_id", "subject", "interval_name_raw", "visit_date", "study")
    list_filter = ("deleted", "study")
    search_fields = ("imednet_id", "subject_key_raw", "interval_name_raw")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "subject",
        "interval",
        "imednet_id",
        "interval_name_raw",
        "subject_key_raw",
        "start_date",
        "end_date",
        "due_date",
        "visit_date",
        "visit_date_form",
        "deleted",
        "visit_date_question",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study", "subject", "interval")


class RecordKeywordInline(admin.TabularInline):
    model = RecordKeyword
    extra = 0
    readonly_fields = ("keyword",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Records.
    """

    list_display = ("subject_key", "form", "record_status", "deleted", "study")
    list_filter = ("record_status", "deleted", "study", "form")
    search_fields = ("subject_key", "imednet_id", "record_oid")
    inlines = [RecordKeywordInline]

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "subject",
        "site",
        "form",
        "interval",
        "visit",
        "imednet_id",
        "record_oid",
        "record_type",
        "record_status",
        "deleted",
        "imednet_subject_id",
        "subject_oid",
        "subject_key",
        "imednet_visit_id",
        "parent_record_id",
        "record_data",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related and prefetch_related to prevent N+1 query degradation.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("study", "subject", "site", "form", "interval", "visit")
            .prefetch_related("keywords")
        )


class QueryCommentInline(admin.TabularInline):
    """
    Read-only inline for QueryComments.
    """

    model = QueryComment
    extra = 0
    readonly_fields = ("comment", "user_raw", "date_created")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Queries.
    """

    list_display = ("imednet_id", "subject", "record", "annotation_type", "description", "study")
    list_filter = ("annotation_type", "study")
    search_fields = ("imednet_id", "subject_key", "description")
    inlines = [QueryCommentInline]

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "subject",
        "record",
        "variable_ref",
        "imednet_id",
        "imednet_subject_id",
        "subject_oid",
        "annotation_type",
        "query_type",
        "description",
        "imednet_record_id",
        "variable_raw",
        "subject_key",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related and prefetch_related to prevent N+1 query degradation.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("study", "subject", "record", "variable_ref")
            .prefetch_related("comments")
        )


@admin.register(Coding)
class CodingAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Codings.
    """

    list_display = ("imednet_id", "subject", "code", "dictionary_name", "study")
    list_filter = ("dictionary_name", "study")
    search_fields = ("imednet_id", "code", "dictionary_name", "subject__subject_key")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "subject",
        "form",
        "variable_ref",
        "coded_by_user",
        "imednet_id",
        "site_name",
        "site_id",
        "imednet_subject_id",
        "revision",
        "imednet_record_id",
        "value",
        "code",
        "reason",
        "dictionary_name",
        "dictionary_version",
        "date_coded",
        "subject_key_raw",
        "variable_raw",
        "coded_by_raw",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study", "subject", "form", "variable_ref", "coded_by_user")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """
    Optimized administrator interface for iMednet Jobs.
    """

    list_display = ("batch_id", "state", "date_created", "study")
    list_filter = ("state", "study")
    search_fields = ("imednet_id", "batch_id", "state")

    # All incoming remote API fields are read-only to ensure data integrity
    readonly_fields = (
        "study",
        "imednet_id",
        "batch_id",
        "state",
        "date_created",
        "date_started",
        "date_finished",
    )

    def get_queryset(self, request):
        """
        Optimize queryset with select_related to prevent N+1 query degradation.
        """
        return super().get_queryset(request).select_related("study")
