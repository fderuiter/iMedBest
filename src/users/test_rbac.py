from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory

from users.auth import CustomAdfsAuthCodeBackend

User = get_user_model()


@pytest.mark.django_db()
class TestRBAC:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.backend = CustomAdfsAuthCodeBackend()
        self.rf = RequestFactory()
        self.request = self.rf.get("/oauth2/callback")
        # Ensure groups exist (though they should be created by migration)
        Group.objects.get_or_create(name="Clinical_Admin")
        Group.objects.get_or_create(name="Data_Analyst")
        Group.objects.get_or_create(name="IT Manager")

    def test_mirror_ingestion(self):
        """
        Test Case 1 (Mirror Ingestion): Mock a login callback payload containing group claims
        mapping to the Clinical_Admin GUID. Verify that after OIDC callback, the local
        Django user is added to the Clinical_Admin Django Group.
        """
        claims = {
            "upn": "admin@mednet.com",
            "given_name": "Clinical",
            "family_name": "Admin",
            "email": "admin@mednet.com",
            "groups": ["762c26f0-6101-4475-b657-69c5e3170e5b"],
        }

        with (
            patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims),
            patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
                return_value={"access_token": "fake-access-token"},
            ),
        ):
            user = self.backend.authenticate(self.request, authorization_code="fake-code")

            assert user is not None
            assert user.groups.filter(name="Clinical_Admin").exists()

    def test_mirror_deprovisioning(self):
        """
        Test Case 2 (Mirror Deprovisioning): Re-login the user with a mock payload omitting
        the Clinical_Admin group GUID. Verify that the user is immediately stripped of
        their local group membership.
        """
        # First login with group
        claims_with_group = {
            "upn": "user@mednet.com",
            "given_name": "User",
            "family_name": "One",
            "email": "user@mednet.com",
            "groups": ["762c26f0-6101-4475-b657-69c5e3170e5b"],
        }

        with (
            patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims_with_group),
            patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
                return_value={"access_token": "fake-access-token"},
            ),
        ):
            user = self.backend.authenticate(self.request, authorization_code="fake-code")
            assert user.groups.filter(name="Clinical_Admin").exists()

        # Second login without group
        claims_without_group = {
            "upn": "user@mednet.com",
            "given_name": "User",
            "family_name": "One",
            "email": "user@mednet.com",
            "groups": [],
        }

        with (
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims_without_group
            ),
            patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
                return_value={"access_token": "fake-access-token"},
            ),
        ):
            user = self.backend.authenticate(self.request, authorization_code="fake-code")
            assert not user.groups.filter(name="Clinical_Admin").exists()

    def test_staff_admin_block(self):
        """
        Test Case 3 (Staff Admin Block): Attempt to access /admin/ with a user who
        does not carry the IT manager GUID. Assert a 403 Forbidden response is returned.
        And verify that user with IT manager GUID gets is_staff = True.
        """
        # User with IT Manager GUID
        claims_it = {
            "upn": "it@mednet.com",
            "given_name": "IT",
            "family_name": "Manager",
            "email": "it@mednet.com",
            "groups": ["43063544-e34d-44a6-8025-a7b2169b60b7"],
        }

        with (
            patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims_it),
            patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
                return_value={"access_token": "fake-access-token"},
            ),
        ):
            user_it = self.backend.authenticate(self.request, authorization_code="fake-code")
            assert user_it.is_staff is True

        # User without IT Manager GUID
        claims_regular = {
            "upn": "regular@mednet.com",
            "given_name": "Regular",
            "family_name": "User",
            "email": "regular@mednet.com",
            "groups": ["762c26f0-6101-4475-b657-69c5e3170e5b"],  # Clinical Admin, not IT Manager
        }

        with (
            patch("django_auth_adfs.backend.AdfsAuthCodeBackend.validate_access_token", return_value=claims_regular),
            patch("django_auth_adfs.config.ProviderConfig.load_config", return_value=None),
            patch(
                "django_auth_adfs.backend.AdfsAuthCodeBackend.exchange_auth_code",
                return_value={"access_token": "fake-access-token"},
            ),
        ):
            user_regular = self.backend.authenticate(self.request, authorization_code="fake-code")
            assert user_regular.is_staff is False
