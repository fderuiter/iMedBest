# ruff: noqa: RUF012
import uuid

from django.db import models


class Job(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    endpoint = models.CharField(max_length=255)
    payload = models.JSONField()
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Metric(models.Model):
    name = models.CharField(max_length=255)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
