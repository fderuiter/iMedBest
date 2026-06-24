from django.contrib.auth.models import AbstractUser
from django.db import models

from .oidc import decrypt, encrypt


class User(AbstractUser):
    is_service_account = models.BooleanField(default=False)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    notifications_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile for {self.user.username}"


class SiteMembership(models.Model):
    ROLE_CHOICES = (("site_investigator", "Site Investigator"),)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_memberships")
    site = models.ForeignKey("clinical.Site", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("user", "site", "role")


class StudyMembership(models.Model):
    ROLE_CHOICES = (("clinical_auditor", "Clinical Auditor"),)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_memberships")
    study = models.ForeignKey("clinical.Study", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("user", "study", "role")


class OIDCConfiguration(models.Model):
    provider_name = models.CharField(max_length=255, unique=True)
    client_id = models.CharField(max_length=255)
    _client_secret = models.TextField(db_column="client_secret")
    discovery_url = models.URLField(help_text="OIDC Provider Discovery URL (/.well-known/openid-configuration)")
    is_active = models.BooleanField(default=True)

    @property
    def client_secret(self):
        return decrypt(self._client_secret)

    @client_secret.setter
    def client_secret(self, value):
        self._client_secret = encrypt(value)
