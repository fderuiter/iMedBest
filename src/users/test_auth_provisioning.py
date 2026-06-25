from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django_auth_adfs.backend import AdfsAuthCodeBackend

User = get_user_model()


@pytest.mark.django_db()
def test_user_provisioning_and_profile_creation():
    """
    Test that a local Django User and its UserProfile are created
    upon a successful OIDC authentication.
    """
    backend = AdfsAuthCodeBackend()
    rf = RequestFactory()
    request = rf.get("/oauth2/callback")

    # Mock claims returned from Entra ID (OIDC payload)
    claims = {
        "upn": "jdoe@mednet.com",
        "given_name": "John",
        "family_name": "Doe",
        "email": "jdoe@mednet.com",
    }

    with (
        patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims),
        patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
        patch(
            "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
            return_value={"access_token": "fake-access-token"},
        ),
    ):
        user = backend.authenticate(request, authorization_code="fake-code")

        assert user is not None
        assert user.username == "jdoe@mednet.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "jdoe@mednet.com"

        # Check if UserProfile was created via signal
        assert hasattr(user, "profile")
        assert user.profile.notifications_enabled is True


@pytest.mark.django_db()
def test_manual_user_creation_triggers_profile_creation():
    """
    Test that manually creating a user also triggers UserProfile creation.
    """
    user = User.objects.create(username="manualuser", email="manual@example.com")
    assert hasattr(user, "profile")
    assert user.profile.notifications_enabled is True
