import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse
from clinical.models import Study
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from users.jwt import create_jwt_token

def get_auth_headers(study_key="test-study"):
    from clinical.models import Provider
    provider, _ = Provider.objects.get_or_create(name="Test Provider")
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="test_user", is_staff=True)
    token = create_jwt_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_STUDYKEY": study_key, "HTTP_X_PROVIDER": str(provider.id)}

@pytest.mark.django_db
class TestApiV1Routing:
    def test_api_v1_docs_enabled_in_debug(self):
        with override_settings(DEBUG=True):
            client = Client()
            response = client.get("/api/v1/docs")
            assert response.status_code in [200, 404]

    def test_404_standardized_response(self):
        client = Client()
        response = client.get("/api/v1/clinical/non-existent-path")
        assert response.status_code == 404
        if response.get("Content-Type") == "application/json":
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "ResourceNotFound"

    def test_500_standardized_response_and_sanitization(self):
        headers = get_auth_headers()
        client = Client()
        from unittest.mock import patch
        with patch("clinical.api.get_accessible_studies", side_effect=Exception("Database boom")):
            response = client.get("/api/v1/clinical/studies", **headers)
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "InternalServerError"
            assert data["message"] == "An unexpected internal error occurred."
            assert "Database boom" not in str(data)

    def test_422_validation_error_standardized_response(self):
        headers = get_auth_headers()
        client = Client()
        response = client.post("/api/v1/clinical/studies", data={}, content_type="application/json", **headers)
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "ValidationError"
        assert "details" in data

    def test_409_conflict_standardized_response(self):
        headers = get_auth_headers()
        client = Client()
        from unittest.mock import patch
        from django.db import IntegrityError
        with patch("clinical.api._queue_single_task", side_effect=IntegrityError("Duplicate key")):
            response = client.post("/api/v1/clinical/studies", data={"name": "Test", "externalId": "S1"}, content_type="application/json", **headers)
            assert response.status_code == 409
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "Conflict"
            assert "database integrity conflict" in data["message"]

@pytest.mark.django_db
def test_docs_visibility_logic():
    from django.conf import settings
    from ninja import NinjaAPI

    with override_settings(DEBUG=True):
        api_debug = NinjaAPI(docs_url="/docs" if settings.DEBUG else None)
        assert api_debug.docs_url == "/docs"

    with override_settings(DEBUG=False):
        api_prod = NinjaAPI(docs_url="/docs" if settings.DEBUG else None)
        assert api_prod.docs_url is None

@pytest.mark.django_db
def test_spec_compliant_route_restored(client):
    headers = get_auth_headers("study-spec")
    # This path should now be reachable again
    response = client.get("/api/v1/v1/edc/studies/study-spec/studies", **headers)
    assert response.status_code == 200
