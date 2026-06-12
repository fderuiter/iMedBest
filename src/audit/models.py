from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("SECURITY", "Security"),
        ("UNAUTH", "Unauth"),
    )

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=255, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)

    agent_did = models.CharField(max_length=255, null=True, blank=True)
    supervisor_did = models.CharField(max_length=255, null=True, blank=True)
    external_transaction_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    cryptographic_signature = models.TextField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    study = models.ForeignKey("clinical.Study", null=True, blank=True, on_delete=models.PROTECT, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.model_name} {self.object_id} by {self.user}"

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Audit logs are immutable and cannot be deleted.")
