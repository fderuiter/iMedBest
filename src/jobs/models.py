import uuid
from django.db import models

class JobStatus(models.TextChoices):
    QUEUED = "Queued", "Queued"
    PROCESSING = "Processing", "Processing"
    COMPLETED = "Completed", "Completed"
    FAILED = "Failed", "Failed"

class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED)
    job_type = models.CharField(max_length=100)
    payload = models.JSONField()
    result = models.JSONField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        
    def __str__(self):
        return f"Job {self.id} ({self.job_type}) - {self.status}"
