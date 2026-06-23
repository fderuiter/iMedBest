from django.db import models


class SyncedResourceBase(models.Model):
    """
    Base class for all models synced from external iMednet endpoints.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Form(SyncedResourceBase):
    """
    Represents an iMednet Form entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_forms",
        help_text="The study this form belongs to.",
    )
    imednet_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="External iMednet ID (formId).")
    form_key = models.CharField(max_length=100, db_index=True, help_text="External form key (formKey).")
    form_name = models.CharField(max_length=255)
    form_type = models.CharField(max_length=100)
    revision = models.IntegerField()
    embedded_log = models.BooleanField(default=False)
    enforce_ownership = models.BooleanField(default=False)
    user_agreement = models.BooleanField(default=False)
    subject_record_report = models.BooleanField(default=False)
    unscheduled_visit = models.BooleanField(default=False)
    other_forms = models.BooleanField(default=False)
    epro_form = models.BooleanField(default=False)
    allow_copy = models.BooleanField(default=False)
    disabled = models.BooleanField(
        default=False, help_text="Indicates if the form is disabled or soft-deleted in iMednet."
    )

    def __str__(self):
        return f"{self.form_name} ({self.form_key})"


class User(SyncedResourceBase):
    """
    Represents an iMednet User entity synced to a specific study.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_users",
        help_text="The study this user belongs to.",
    )
    imednet_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="External iMednet ID (userId).")
    login = models.CharField(max_length=150, unique=True, db_index=True, help_text="User login name.")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=255)
    user_active_in_study = models.BooleanField(default=True, help_text="Indicates if the user is active in the study.")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.login})"


class UserRole(models.Model):
    """
    Represents a role assigned to an iMednet User.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="roles")
    role_name = models.CharField(max_length=255)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.role_name} for {self.user.login}"


class RecordRevision(SyncedResourceBase):
    """
    Represents an iMednet RecordRevision entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_record_revisions",
        help_text="The study this record revision belongs to.",
    )
    subject = models.ForeignKey(
        "clinical.Subject",
        on_delete=models.PROTECT,
        related_name="imednet_record_revisions",
        help_text="The subject this record revision belongs to.",
    )
    record = models.ForeignKey(
        "clinical.Record",
        on_delete=models.PROTECT,
        related_name="imednet_record_revisions",
        help_text="The record this revision belongs to.",
    )
    user_profile = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="record_revisions",
        help_text="The user profile associated with this revision.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (recordRevisionId)."
    )
    imednet_record_id = models.IntegerField(help_text="External record ID (recordId).")
    record_oid = models.CharField(max_length=255, help_text="External record OID.")
    record_revision = models.IntegerField(help_text="Record revision number.")
    data_revision = models.IntegerField(help_text="Data revision number.")
    record_status = models.CharField(max_length=255, help_text="Status of the record.")
    imednet_subject_id = models.IntegerField(help_text="External subject ID.")
    subject_oid = models.CharField(max_length=255, help_text="External subject OID.")
    subject_key = models.CharField(max_length=100, db_index=True, help_text="External subject key.")
    site_id = models.IntegerField(help_text="External site ID.")
    form_key = models.CharField(max_length=100, db_index=True, help_text="External form key.")
    interval_id = models.IntegerField(null=True, blank=True, help_text="External interval ID.")
    role = models.CharField(max_length=255, null=True, blank=True, help_text="Role associated with the revision.")
    user_raw = models.CharField(max_length=255, null=True, blank=True, help_text="Raw user information.")
    reason_for_change = models.TextField(blank=True, help_text="Reason for change.")
    deleted = models.BooleanField(default=False, help_text="Indicates if the revision is deleted in iMednet.")

    def __str__(self):
        return f"Revision {self.record_revision} for Record {self.record_id} ({self.record_status})"


class Interval(SyncedResourceBase):
    """
    Represents an iMednet Interval entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_intervals",
        help_text="The study this interval belongs to.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (intervalId)."
    )
    interval_name = models.CharField(max_length=255)
    interval_description = models.TextField(blank=True)
    interval_sequence = models.IntegerField()
    interval_group_id = models.IntegerField()
    interval_group_name = models.CharField(max_length=255)
    timeline = models.CharField(max_length=100)
    defined_using_interval = models.CharField(max_length=255, blank=True)
    window_calculation_form = models.CharField(max_length=255, blank=True)
    window_calculation_date = models.CharField(max_length=255, blank=True)
    actual_date_form = models.CharField(max_length=255, blank=True)
    actual_date = models.CharField(max_length=255, blank=True)
    due_date_will_be_in = models.IntegerField(null=True, blank=True)
    negative_slack = models.IntegerField(null=True, blank=True)
    positive_slack = models.IntegerField(null=True, blank=True)
    epro_grace_period = models.IntegerField(null=True, blank=True)
    disabled = models.BooleanField(
        default=False, help_text="Indicates if the interval is disabled or soft-deleted in iMednet."
    )
    forms = models.ManyToManyField(Form, through="IntervalForm", related_name="intervals")

    def __str__(self):
        return f"{self.interval_name} (Sequence: {self.interval_sequence})"


class IntervalForm(models.Model):
    """
    Explicit through model for the Many-to-Many relationship between Interval and Form.
    """

    interval = models.ForeignKey(Interval, on_delete=models.CASCADE)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("interval", "form")

    def __str__(self):
        return f"{self.interval.interval_name} - {self.form.form_name}"
