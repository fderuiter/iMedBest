from django.db import models


class Study(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Site(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Subject(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name or self.external_id
