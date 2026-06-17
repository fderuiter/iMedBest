from django.db import models
from django.conf import settings

class CommerceAgent(models.Model):
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("MAINTENANCE", "Maintenance"),
    )

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    fetch_address = models.CharField(max_length=255, unique=True)
    wallet_address = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="INACTIVE")
    last_ping = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agents")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.status})"

class CommerceTransaction(models.Model):
    transaction_id = models.CharField(max_length=255, unique=True)
    agent = models.ForeignKey(CommerceAgent, on_delete=models.CASCADE, related_name="transactions")
    item_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tx {self.transaction_id} by {self.agent.name}"

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    embedding_id = models.CharField(max_length=255, null=True, blank=True) # UUID in Qdrant

    def __str__(self):
        return self.name
