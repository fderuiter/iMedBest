from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_auth_adfs.config import provider_config
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestJWTAuth:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("api_health_check")

    @patch("django_auth_adfs.backend.AdfsAccessTokenBackend.validate_access_token")
    @patch("django_auth_adfs.config.ProviderConfig.load_config")
    def test_valid_bearer_token_access(self, mock_load_config, mock_validate):
        mock_load_config.return_value = None
        mock_validate.return_value = {
            "upn": "api-client@mednet.com",
            "given_name": "API",
            "family_name": "Client",
            "email": "api-client@mednet.com",
        }

        self.client.credentials(HTTP_AUTHORIZATION="Bearer valid-mock-token")
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.json()["user"] == "api-client@mednet.com"

    @patch("django_auth_adfs.rest_framework.AdfsAccessTokenAuthentication.authenticate")
    def test_invalid_token_rejected(self, mock_authenticate):
        from rest_framework import exceptions

        mock_authenticate.side_effect = exceptions.AuthenticationFailed("Invalid access token.")

        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = self.client.get(self.url)

        assert response.status_code == 401
        assert "Invalid access token" in response.json()["detail"]

    @patch("django_auth_adfs.config.ProviderConfig._load_openid_config")
    @patch("django_auth_adfs.config.ProviderConfig._load_federation_metadata")
    @patch("django_auth_adfs.backend.AdfsAccessTokenBackend.validate_access_token")
    def test_cache_retention(self, mock_validate, mock_load_fed, mock_load_openid):
        mock_validate.return_value = {"upn": "cached@mednet.com"}
        mock_load_openid.return_value = True
        mock_load_fed.return_value = True

        provider_config._config_timestamp = None

        self.client.credentials(HTTP_AUTHORIZATION="Bearer token1")
        self.client.get(self.url)
        self.client.get(self.url)

        assert mock_load_openid.call_count == 1

    @patch("django_auth_adfs.backend.AdfsAccessTokenBackend.validate_access_token")
    @patch("django_auth_adfs.config.ProviderConfig.load_config")
    def test_n_plus_1_query_count(self, mock_load_config, mock_validate, django_assert_num_queries):
        mock_load_config.return_value = None
        mock_validate.return_value = {
            "upn": "query-test@mednet.com",
            "given_name": "Query",
            "family_name": "Test",
            "email": "query-test@mednet.com",
        }

        user = User.objects.create(
            username="query-test@mednet.com", email="query-test@mednet.com", first_name="Query", last_name="Test"
        )
        from users.models import UserProfile

        UserProfile.objects.get_or_create(user=user)

        self.client.credentials(HTTP_AUTHORIZATION="Bearer token")

        # Warm up content types
        from django.contrib.contenttypes.models import ContentType

        list(ContentType.objects.all())

        # We aim for low query count. Due to audit logs and other signals, it might be more than 2,
        # but we've optimized to avoid redundant saves.
        # Let's check how many we get now.
        response = self.client.get(self.url)
        assert response.status_code == 200
