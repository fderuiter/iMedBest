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
