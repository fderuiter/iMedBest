import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class ClinicalEntity(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Longitudinal Reconstruction Metadata
    clinical_timestamp = models.DateTimeField(null=True, blank=True)
    source_sequence = models.IntegerField(null=True, blank=True)
    offset_days = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if hasattr(self, "get_subject") and self.clinical_timestamp:
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


class SyncStatus(models.Model):
    last_successful_pull = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, default="UNKNOWN")
    error_message = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync Status: {self.status}"


@receiver(post_save, sender=Record)
def create_record_revision(sender, instance, created, **kwargs):
    RecordRevision.objects.create(
        external_id=str(uuid.uuid4()),
        record=instance,
        value=instance.value,
        clinical_timestamp=instance.clinical_timestamp,
        source_sequence=instance.source_sequence,
        offset_days=instance.offset_days,
    )
