from django.contrib.auth.models import AbstractUser
from django.db import models

from .oidc import decrypt, encrypt


class User(AbstractUser):
    pass


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
