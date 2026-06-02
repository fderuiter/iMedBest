import uuid
from typing import ClassVar

from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Provider(models.Model):
    name = models.CharField(max_length=255, unique=True)
    api_endpoint = models.URLField(blank=True, null=True)
    auth_protocol = models.CharField(
        max_length=50, blank=True, null=True, choices=[("OIDC", "OIDC"), ("API_KEY", "API Key"), ("OAUTH2", "OAuth2")]
    )
    auth_credentials = models.JSONField(
        blank=True, null=True, help_text="Store provider-specific API and authentication details here."
    )
    hierarchy_mapping = models.JSONField(
        default=dict, blank=True, help_text="Maps external vendor hierarchy to internal clinical models."
    )
    schema_mapping = models.JSONField(
        default=dict, blank=True, help_text="Maps external data fields to internal clinical attributes."
    )

    def __str__(self):
        return self.name


class ClinicalEntityQuerySet(models.QuerySet):
    def delete(self):
        for obj in self:
            obj.delete()

    def hard_delete(self):
        return super().delete()


    def restore(self):
        for obj in self:
            obj.restore()


class ActiveManager(models.Manager):
    def get_queryset(self):
        return ClinicalEntityQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllManager(models.Manager):
    def get_queryset(self):
        return ClinicalEntityQuerySet(self.model, using=self._db)


class ClinicalEntity(models.Model):
    pii_fields = []
    external_id = models.CharField(max_length=255)
    provider = models.ForeignKey("clinical.Provider", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "users.User", on_delete=models.PROTECT, related_name="%(class)s_created", null=True, blank=True
    )
    updated_by = models.ForeignKey(
        "users.User", on_delete=models.PROTECT, related_name="%(class)s_updated", null=True, blank=True
    )

    # Longitudinal Reconstruction Metadata
    clinical_timestamp = models.DateTimeField(null=True, blank=True)
    source_sequence = models.IntegerField(null=True, blank=True)
    offset_days = models.IntegerField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = AllManager()


    class Meta:
        abstract = True
        constraints: ClassVar[list] = [

            models.UniqueConstraint(
                fields=["provider", "external_id"], name="%(app_label)s_%(class)s_unique_provider_external_id"
            )
        ]

    def delete(self, using=None, keep_parents=False, deleted_at=None):
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = deleted_at or timezone.now()
            self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

            # Cascade to children
            for related_object in self._meta.related_objects:
                if related_object.on_delete == models.CASCADE:
                    # Dynamically fetch children
                    related_model = related_object.related_model
                    if hasattr(related_model, "all_objects"):
                        filter_kwargs = {related_object.field.name: self}
                        for child in related_model.all_objects.filter(**filter_kwargs, is_deleted=False):
                            child.delete(deleted_at=self.deleted_at)


    def get_study(self):
        if self.__class__.__name__ == "Study":
            return self
        if self.__class__.__name__ == "Site":
            return self.study
        if self.__class__.__name__ == "Subject":
            return self.site.study
        if self.__class__.__name__ in ["Form", "Interval"]:
            return self.study
        if self.__class__.__name__ == "Variable":
            return self.form.study
        if hasattr(self, "get_subject"):
            subj = self.get_subject()
            if subj:
                return subj.site.study
        return None

    def restore(self):
        if self.is_deleted:
            # Check if parent is deleted
            for field in self._meta.fields:
                if isinstance(field, models.ForeignKey) and field.remote_field.on_delete == models.CASCADE:
                    parent = getattr(self, field.name)
                    if parent and getattr(parent, "is_deleted", False):
                        raise ValueError(
                            f"Cannot restore {self._meta.model_name} because its parent {field.name} is deleted."
                        )

            target_deleted_at = self.deleted_at

            self.is_deleted = False
            self.deleted_at = None
            self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

            # Restore children that were deleted at exactly the same time
            if target_deleted_at:
                for related_object in self._meta.related_objects:
                    if related_object.on_delete == models.CASCADE:
                        related_model = related_object.related_model
                        if hasattr(related_model, "all_objects"):
                            filter_kwargs = {related_object.field.name: self}
                            for child in related_model.all_objects.filter(
                                **filter_kwargs, is_deleted=True, deleted_at=target_deleted_at
                            ):
                                child.restore()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = self.__class__.all_objects.get(pk=self.pk)
            if orig.created_by_id and self.created_by_id != orig.created_by_id:
                self.created_by_id = orig.created_by_id

        if hasattr(self, "get_subject") and self.clinical_timestamp:
            try:
                subject = self.get_subject()
                if subject:
                    baseline = subject.baseline_date
                    if baseline:
                        self.offset_days = (self.clinical_timestamp.date() - baseline.date()).days
            except Exception:  # noqa: S110
                pass
        super().save(*args, **kwargs)


# Level 1

class Study(ClinicalEntity):
    name = models.CharField(max_length=255)
    pii_masking_enabled = models.BooleanField(default=False)

    class Meta:
        permissions = [
            ("view_pii", "Can view unmasked PII"),
        ]

    def __str__(self):

        return self.name


class Site(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# Level 2
class Subject(ClinicalEntity):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=255, blank=True)
    pii_fields = ["name"]

    @property
    def baseline_date(self):
        """
        The "Day 0" baseline event for a subject is defined as the clinical_timestamp
        of the chronologically earliest Visit. If no visits have timestamps, returns None.
        """
        first_visit = self.visits.filter(clinical_timestamp__isnull=False).order_by("clinical_timestamp").first()
        return first_visit.clinical_timestamp if first_visit else None

    def __str__(self):
        return self.name or self.external_id


class Form(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="forms")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Interval(ClinicalEntity):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="intervals")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# Level 3
class Variable(ClinicalEntity):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="variables")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Visit(ClinicalEntity):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="visits")
    interval = models.ForeignKey(Interval, on_delete=models.CASCADE, related_name="visits")

    def __str__(self):
        return f"{self.subject} - {self.interval}"

    def get_subject(self):
        return self.subject


# Level 4
class Record(ClinicalEntity):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="records")
    variable = models.ForeignKey(Variable, on_delete=models.CASCADE, related_name="records")
    value = models.TextField(blank=True)
    pii_fields = ["value"]

    def get_subject(self):
        return self.visit.subject


class Coding(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="codings")
    code = models.CharField(max_length=255)

    def get_subject(self):
        return self.record.visit.subject


class Query(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="queries")
    text = models.TextField()
    status = models.CharField(max_length=50, default="OPEN")  # e.g. OPEN, RESOLVED
    previous_status = models.CharField(max_length=50, null=True, blank=True)
    sync_status = models.CharField(max_length=50, default="CONFIRMED")  # PENDING, CONFIRMED, SYNC_FAILED
    last_sync_error = models.TextField(null=True, blank=True)

    def get_subject(self):
        return self.record.visit.subject


class RecordRevision(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="revisions")
    value = models.TextField()
    pii_fields = ["value"]

    def get_subject(self):
        return self.record.visit.subject



@receiver(post_save, sender=Record)
def create_record_revision(sender, instance, created, **kwargs):
    value_to_save = instance.value
    study = instance.get_study()
    if (
        study
        and getattr(study, "pii_masking_enabled", False)
        and hasattr(instance, "pii_fields")
        and "value" in instance.pii_fields
        and value_to_save
    ):
        value_to_save = "[REDACTED]"

    RecordRevision.objects.create(
        external_id=str(uuid.uuid4()),
        provider=instance.provider,
        record=instance,
        value=value_to_save,
        clinical_timestamp=instance.clinical_timestamp,
        source_sequence=instance.source_sequence,
        offset_days=instance.offset_days,
        created_by=instance.updated_by,
        updated_by=instance.updated_by,
    )



@receiver(post_save, sender=Visit)
def trigger_longitudinal_reconstruction(sender, instance, created, update_fields, **kwargs):
    # If the visit is saved, it might be a new baseline or an updated baseline
    if created or (update_fields and "clinical_timestamp" in update_fields) or not update_fields:
        from clinical.tasks import reconstruct_subject_timeline

        transaction.on_commit(lambda: reconstruct_subject_timeline.delay(instance.subject.id))


class BufferedOrphan(models.Model):
    provider = models.ForeignKey("clinical.Provider", on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=50)
    missing_parent_id = models.CharField(max_length=255)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"BufferedOrphan {self.entity_type} waiting for {self.missing_parent_id}"


class SyncJob(models.Model):
    provider = models.ForeignKey("clinical.Provider", on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=50,
        default="PENDING",
        choices=[
            ("PENDING", "Pending"),
            ("PROCESSING", "Processing"),
            ("COMPLETED", "Completed"),
            ("FAILED", "Failed"),
        ],
    )
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Job {self.id} - {self.status}"


class SyncTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name="tasks")
    dependencies = models.ManyToManyField("self", symmetrical=False, related_name="dependents", blank=True)
    entity_type = models.CharField(max_length=50)  # e.g. 'Study', 'Subject'
    payload = models.JSONField()
    status = models.CharField(
        max_length=50,
        default="PENDING",
        choices=[
            ("PENDING", "Pending"),
            ("PROCESSING", "Processing"),
            ("COMPLETED", "Completed"),
            ("FAILED", "Failed"),
        ],
    )
    parent_task = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="child_tasks")
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task {self.id} for {self.entity_type} - {self.status}"


class ExportJob(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    status = models.CharField(max_length=50, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    file_path = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)


class ValidationRule(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    rule_dsl = models.JSONField(help_text="JSON DSL for defining validation logic")
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (v{self.version})"


class ValidationResult(models.Model):
    rule = models.ForeignKey(ValidationRule, on_delete=models.CASCADE, related_name="results")
    job = models.ForeignKey(
        SyncJob, on_delete=models.CASCADE, null=True, blank=True, related_name="validation_results"
    )
    passed = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    query = models.ForeignKey(
        Query, on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_results"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.rule.name}: {'Passed' if self.passed else 'Failed'}"
