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
        help_text="The study this form belongs to."
    )
    imednet_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="External iMednet ID (formId)."
    )
    form_key = models.CharField(
        max_length=100,
        db_index=True,
        help_text="External form key (formKey)."
    )
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
        default=False,
        help_text="Indicates if the form is disabled or soft-deleted in iMednet."
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
        help_text="The study this user belongs to."
    )
    imednet_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="External iMednet ID (userId)."
    )
    login = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="User login name."
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=255)
    user_active_in_study = models.BooleanField(
        default=True,
        help_text="Indicates if the user is active in the study."
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.login})"


class UserRole(models.Model):
    """
    Represents a role assigned to an iMednet User.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="roles"
    )
    role_name = models.CharField(max_length=255)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.role_name} for {self.user.login}"
