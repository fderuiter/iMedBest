from django.db import models

from core.logging import get_logger

logger = get_logger(__name__)


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


class Variable(SyncedResourceBase):
    """
    Represents an iMednet Variable entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_variables",
        help_text="The study this variable belongs to.",
    )
    form = models.ForeignKey(
        Form,
        on_delete=models.PROTECT,
        related_name="variables",
        null=True,
        blank=True,
        help_text="The form this variable belongs to.",
    )
    form_key_raw = models.CharField(
        max_length=255,
        blank=True,
        help_text="Raw form ID from iMednet, used for error tracking if form lookup fails.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (variableId)."
    )
    variable_type = models.CharField(max_length=100)
    variable_name = models.CharField(max_length=255)
    sequence = models.IntegerField()
    revision = models.IntegerField()
    disabled = models.BooleanField(default=False)
    variable_oid = models.CharField(max_length=255, unique=True, db_index=True)
    deleted = models.BooleanField(default=False)
    label = models.TextField(blank=True)
    blinded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.variable_name} ({self.variable_oid})"


class Subject(SyncedResourceBase):
    """
    Represents an iMednet Subject entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_subjects",
        help_text="The study this subject belongs to.",
    )
    site = models.ForeignKey(
        "clinical.Site",
        on_delete=models.PROTECT,
        related_name="imednet_subjects",
        null=True,
        blank=True,
        help_text="The site this subject belongs to.",
    )
    site_name_raw = models.CharField(
        max_length=255,
        blank=True,
        help_text="Raw site name from iMednet, used for error tracking if site lookup fails.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (subjectId)."
    )
    subject_oid = models.CharField(max_length=255, help_text="External subject OID.")
    subject_key = models.CharField(max_length=100, unique=True, db_index=True, help_text="External subject key.")
    subject_status = models.CharField(max_length=100, help_text="Status of the subject.")
    enrollment_start_date = models.DateTimeField(null=True, blank=True, help_text="Enrollment start date.")
    date_of_birth = models.DateField(null=True, blank=True, db_index=True)
    deleted = models.BooleanField(default=False, help_text="Indicates if the subject is deleted in iMednet.")

    def __str__(self):
        return f"{self.subject_key} ({self.subject_status})"


class SubjectKeyword(models.Model):
    """
    Represents a keyword tag associated with a Subject.
    """

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="keywords")
    keyword = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.keyword} for {self.subject.subject_key}"


class Visit(SyncedResourceBase):
    """
    Represents an iMednet Visit entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_visits",
        help_text="The study this visit belongs to.",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="imednet_visits",
        help_text="The subject this visit belongs to.",
    )
    interval = models.ForeignKey(
        Interval,
        on_delete=models.PROTECT,
        related_name="imednet_visits",
        help_text="The interval this visit belongs to.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (visitId)."
    )
    interval_name_raw = models.CharField(max_length=255)
    subject_key_raw = models.CharField(max_length=100)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True)
    visit_date_form = models.CharField(max_length=255, blank=True)
    deleted = models.BooleanField(default=False)
    visit_date_question = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Visit {self.imednet_id} (Subject: {self.subject_key_raw}, Interval: {self.interval_name_raw})"


class Record(SyncedResourceBase):
    """
    Represents an iMednet Record entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_records",
        help_text="The study this record belongs to.",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="imednet_records",
        help_text="The subject this record belongs to.",
    )
    site = models.ForeignKey(
        "clinical.Site",
        on_delete=models.PROTECT,
        related_name="imednet_records",
        help_text="The site this record belongs to.",
    )
    form = models.ForeignKey(
        Form,
        on_delete=models.PROTECT,
        related_name="imednet_records",
        help_text="The form this record belongs to.",
    )
    interval = models.ForeignKey(
        Interval,
        on_delete=models.PROTECT,
        related_name="imednet_records",
        help_text="The interval this record belongs to.",
    )
    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="imednet_records",
        null=True,
        blank=True,
        help_text="The visit this record belongs to.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External record ID (recordId)."
    )
    record_oid = models.CharField(max_length=255, blank=True, help_text="External record OID.")
    record_type = models.CharField(max_length=100, help_text="Type of the record.")
    record_status = models.CharField(max_length=255, help_text="Status of the record.")
    deleted = models.BooleanField(default=False, help_text="Indicates if the record is deleted in iMednet.")
    imednet_subject_id = models.IntegerField(help_text="External subject ID (subjectId).")
    subject_oid = models.CharField(max_length=255, blank=True, help_text="External subject OID.")
    subject_key = models.CharField(max_length=100, db_index=True, help_text="External subject key.")
    imednet_visit_id = models.IntegerField(null=True, blank=True, help_text="External visit ID (visitId).")
    parent_record_id = models.IntegerField(null=True, blank=True, help_text="External parent record ID.")
    record_data = models.JSONField(default=dict, blank=True, help_text="Schema-less record data.")

    def __str__(self):
        return f"Record {self.imednet_id} (Form: {self.form}, Status: {self.record_status})"

    def save(self, *args, **kwargs):
        # Dynamic Variable Validation
        if self.form_id:
            # Get valid variable names for this form
            valid_vars = set(Variable.objects.filter(form=self.form).values_list("variable_name", flat=True))
            for key in self.record_data:
                if key not in valid_vars:
                    logger.warning(
                        "unknown_variable_in_record_data",
                        record_id=self.imednet_id,
                        form_id=self.form.imednet_id,
                        variable_name=key,
                    )
        super().save(*args, **kwargs)


class RecordKeyword(models.Model):
    """
    Represents a keyword tag associated with a Record.
    """

    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="keywords")
    keyword = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.keyword} for Record {self.record.imednet_id}"


class Coding(SyncedResourceBase):
    """
    Represents an iMednet Coding entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_codings",
        help_text="The study this coding belongs to.",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="imednet_codings",
        help_text="The subject this coding belongs to.",
    )
    form = models.ForeignKey(
        Form,
        on_delete=models.PROTECT,
        related_name="imednet_codings",
        help_text="The form this coding belongs to.",
    )
    variable_ref = models.ForeignKey(
        Variable,
        on_delete=models.PROTECT,
        related_name="imednet_codings",
        help_text="The variable reference this coding belongs to.",
    )
    coded_by_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="imednet_codings",
        help_text="The user who performed the coding.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (codingId)."
    )
    site_name = models.CharField(max_length=255)
    site_id = models.IntegerField()
    imednet_subject_id = models.IntegerField(help_text="External subject ID (subjectId).")
    revision = models.IntegerField()
    imednet_record_id = models.IntegerField(help_text="External record ID (recordId).")
    value = models.TextField()
    code = models.TextField()
    reason = models.TextField(blank=True)
    dictionary_name = models.CharField(max_length=100, db_index=True)
    dictionary_version = models.CharField(max_length=50)
    date_coded = models.DateTimeField()
    subject_key_raw = models.CharField(
        max_length=100, blank=True, help_text="Raw subject key backup for error tracking."
    )
    variable_raw = models.CharField(max_length=255, blank=True, help_text="Raw variable backup for error tracking.")
    coded_by_raw = models.CharField(max_length=255, blank=True, help_text="Raw user backup for error tracking.")

    def __str__(self):
        return f"Coding {self.imednet_id} ({self.code})"


class Query(SyncedResourceBase):
    """
    Represents an iMednet Query entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_queries",
        help_text="The study this query belongs to.",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="imednet_queries",
        help_text="The subject this query belongs to.",
    )
    record = models.ForeignKey(
        Record,
        on_delete=models.PROTECT,
        related_name="imednet_queries",
        null=True,
        blank=True,
        help_text="The record this query belongs to.",
    )
    variable_ref = models.ForeignKey(
        Variable,
        on_delete=models.PROTECT,
        related_name="imednet_queries",
        null=True,
        blank=True,
        help_text="The variable reference this query belongs to.",
    )
    imednet_id = models.CharField(
        max_length=255, unique=True, db_index=True, help_text="External iMednet ID (annotationId)."
    )
    imednet_subject_id = models.IntegerField(help_text="External subject ID (subjectId).")
    subject_oid = models.CharField(max_length=255, help_text="External subject OID (subjectOid).")
    annotation_type = models.CharField(max_length=100, help_text="Type of annotation (annotationType).")
    query_type = models.CharField(
        max_length=100, null=True, blank=True, help_text="Specific query type if applicable (type)."
    )
    description = models.TextField(help_text="Query description.")
    imednet_record_id = models.IntegerField(null=True, blank=True, help_text="External record ID (recordId).")
    variable_raw = models.CharField(max_length=100, help_text="Raw variable name from iMednet.")
    subject_key = models.CharField(max_length=100, db_index=True, help_text="External subject key (subjectKey).")

    def __str__(self):
        return f"Query {self.imednet_id} ({self.annotation_type})"


class QueryComment(models.Model):
    """
    Represents a comment associated with an iMednet Query.
    """

    query = models.ForeignKey(Query, on_delete=models.CASCADE, related_name="comments")
    comment = models.TextField()
    user_raw = models.CharField(max_length=255, help_text="Raw user information from iMednet.")
    date_created = models.DateTimeField(help_text="The date and time the comment was created.")

    def __str__(self):
        return f"Comment for Query {self.query.imednet_id} by {self.user_raw}"


class Job(SyncedResourceBase):
    """
    Represents an iMednet Job entity.
    """

    study = models.ForeignKey(
        "clinical.Study",
        on_delete=models.PROTECT,
        related_name="imednet_jobs",
        help_text="The study this job belongs to.",
    )
    imednet_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="External iMednet ID (jobId).")
    batch_id = models.CharField(max_length=255, db_index=True, help_text="External batch ID (batchId).")
    state = models.CharField(max_length=100)
    date_created = models.DateTimeField()
    date_started = models.DateTimeField(null=True, blank=True)
    date_finished = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job {self.imednet_id} ({self.state})"
