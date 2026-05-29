import uuid

from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone



class Provider(models.Model):
    name = models.CharField(max_length=255, unique=True)
    api_endpoint = models.URLField(blank=True, null=True)
    auth_protocol = models.CharField(max_length=50, blank=True, null=True, choices=[
        ('OIDC', 'OIDC'),
        ('API_KEY', 'API Key'),
        ('OAUTH2', 'OAuth2')
    ])
    auth_credentials = models.JSONField(blank=True, null=True, help_text="Store provider-specific API and authentication details here.")
    hierarchy_mapping = models.JSONField(default=dict, blank=True, help_text="Maps external vendor hierarchy to internal clinical models.")
    schema_mapping = models.JSONField(default=dict, blank=True, help_text="Maps external data fields to internal clinical attributes.")

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
    external_id = models.CharField(max_length=255)
    provider = models.ForeignKey("clinical.Provider", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
        null=True,
        blank=True
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
        constraints = [
            models.UniqueConstraint(fields=['provider', 'external_id'], name='%(app_label)s_%(class)s_unique_provider_external_id')
        ]

    def delete(self, using=None, keep_parents=False, deleted_at=None):
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = deleted_at or timezone.now()
            self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

            # Cascade to children
            for related_object in self._meta.related_objects:
                if related_object.on_delete == models.CASCADE:
                    # Dynamically fetch children
                    related_model = related_object.related_model
                    if hasattr(related_model, 'all_objects'):
                        filter_kwargs = {related_object.field.name: self}
                        for child in related_model.all_objects.filter(**filter_kwargs, is_deleted=False):
                            child.delete(deleted_at=self.deleted_at)

    def restore(self):
        if self.is_deleted:
            # Check if parent is deleted
            for field in self._meta.fields:
                if isinstance(field, models.ForeignKey) and field.remote_field.on_delete == models.CASCADE:
                    parent = getattr(self, field.name)
                    if parent and getattr(parent, 'is_deleted', False):
                        raise ValueError(f"Cannot restore {self._meta.model_name} because its parent {field.name} is deleted.")

            target_deleted_at = self.deleted_at

            self.is_deleted = False
            self.deleted_at = None
            self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

            # Restore children that were deleted at exactly the same time
            if target_deleted_at:
                for related_object in self._meta.related_objects:
                    if related_object.on_delete == models.CASCADE:
                        related_model = related_object.related_model
                        if hasattr(related_model, 'all_objects'):
                            filter_kwargs = {related_object.field.name: self}
                            for child in related_model.all_objects.filter(**filter_kwargs, is_deleted=True, deleted_at=target_deleted_at):
                                child.restore()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = self.__class__.all_objects.get(pk=self.pk)
            if orig.created_by_id and self.created_by_id != orig.created_by_id:
                self.created_by_id = orig.created_by_id

        if hasattr(self, 'get_subject') and self.clinical_timestamp:
            try:
                subject = self.get_subject()
                if subject:
                    baseline = subject.baseline_date
                    if baseline:
                        self.offset_days = (self.clinical_timestamp.date() - baseline.date()).days
            except Exception:
                pass
        super().save(*args, **kwargs)


# Level 1
class Study(ClinicalEntity):
    name = models.CharField(max_length=255)

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

    @property
    def baseline_date(self):
        """
        The "Day 0" baseline event for a subject is defined as the clinical_timestamp
        of the chronologically earliest Visit. If no visits have timestamps, returns None.
        """
        first_visit = self.visits.filter(clinical_timestamp__isnull=False).order_by('clinical_timestamp').first()
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

    def get_subject(self):
        return self.record.visit.subject


class RecordRevision(ClinicalEntity):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="revisions")
    value = models.TextField()

    def get_subject(self):
        return self.record.visit.subject



@receiver(post_save, sender=Record)
def create_record_revision(sender, instance, created, **kwargs):
    RecordRevision.objects.create(
        external_id=str(uuid.uuid4()),
        record=instance,
        value=instance.value,
        clinical_timestamp=instance.clinical_timestamp,
        source_sequence=instance.source_sequence,
        offset_days=instance.offset_days,
        created_by=instance.updated_by,
        updated_by=instance.updated_by
    )

@receiver(post_save, sender=Visit)
def trigger_longitudinal_reconstruction(sender, instance, created, update_fields, **kwargs):
    # If the visit is saved, it might be a new baseline or an updated baseline
    if created or (update_fields and 'clinical_timestamp' in update_fields) or not update_fields:
        from clinical.tasks import reconstruct_subject_timeline
        transaction.on_commit(lambda: reconstruct_subject_timeline.delay(instance.subject.id))


class BufferedOrphan(models.Model):
    provider = models.ForeignKey("clinical.Provider", on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=50)
    missing_parent_id = models.CharField(max_length=255)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"BufferedOrphan {self.entity_type} waiting for {self.missing_parent_id}"

class SyncJob(models.Model):
    provider = models.ForeignKey("clinical.Provider", on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=50, default='PENDING', choices=[
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ])
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Job {self.id} - {self.status}"

class SyncTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name='tasks')
    hierarchy_level = models.IntegerField() # 1=Study/Site, 2=Subject/Form/Interval, 3=Variable/Visit, 4=Record/etc
    entity_type = models.CharField(max_length=50) # e.g. 'Study', 'Subject'
    payload = models.JSONField()
    status = models.CharField(max_length=50, default='PENDING', choices=[
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ])
    parent_task = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_tasks')
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task {self.id} for {self.entity_type} - {self.status}"

