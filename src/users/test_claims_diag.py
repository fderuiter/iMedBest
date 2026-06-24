import contextlib
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from users.auth import CustomAdfsAuthCodeBackend

User = get_user_model()


@pytest.mark.django_db
def test_service_principal_claims_logic():
    backend = CustomAdfsAuthCodeBackend()
    rf = RequestFactory()
    request = rf.get("/oauth2/callback")

    # Mock claims for a service principal
    # Typically no 'upn', but has 'oid' and 'appid'
    claims = {
        "oid": "service-principal-oid",
        "appid": "client-app-id",
        "roles": ["Clinical_Admin"],
        "tid": "tenant-id",
        "iss": "issuer",
        "aud": "audience",
    }

    # We want to see how the backend behaves when 'upn' is missing
    # Since base.py has USERNAME_CLAIM = "upn"

    with (
        patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims),
        patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
        patch(
            "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
            return_value={"access_token": "fake-access-token"},
        ),
        contextlib.suppress(Exception),
    ):
        backend.authenticate(request, authorization_code="fake-code")


if __name__ == "__main__":
    # This is just for my diagnostic
    pass
