from unittest.mock import patch

import pytest

from .models import Record


@pytest.fixture(autouse=True)
def mock_auth():
    def fake_auth(self, request, token):
        if token != "test_token":
            return None
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(username='testuser')
        request.user = user
        return token

    with patch('users.auth.OIDCBearer.authenticate', new=fake_auth):
        yield

@pytest.mark.django_db
def test_multi_level_data_import(client):
    # Level 1
    study_resp = client.post(
        "/api/clinical/studies",
        data={"external_id": "study-1", "name": "Study 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert study_resp.status_code == 200

    site_resp = client.post(
        "/api/clinical/sites",
        data={"external_id": "site-1", "study_ext_id": "study-1", "name": "Site 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert site_resp.status_code == 200

    # Level 2
    subject_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-1", "site_ext_id": "site-1", "name": "Subject 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert subject_resp.status_code == 200

    form_resp = client.post(
        "/api/clinical/forms",
        data={"external_id": "form-1", "study_ext_id": "study-1", "name": "Form 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert form_resp.status_code == 200

    int_resp = client.post(
        "/api/clinical/intervals",
        data={"external_id": "int-1", "study_ext_id": "study-1", "name": "Interval 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert int_resp.status_code == 200

    # Level 3
    var_resp = client.post(
        "/api/clinical/variables",
        data={"external_id": "var-1", "form_ext_id": "form-1", "name": "Variable 1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert var_resp.status_code == 200

    visit_resp = client.post(
        "/api/clinical/visits",
        data={"external_id": "visit-1", "subject_ext_id": "sub-1", "interval_ext_id": "int-1"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert visit_resp.status_code == 200

    # Level 4
    record_resp = client.post(
        "/api/clinical/records",
        data={"external_id": "rec-1", "visit_ext_id": "visit-1", "variable_ext_id": "var-1", "value": "120/80"},
        content_type="application/json", HTTP_AUTHORIZATION="Bearer test_token",
    )
    assert record_resp.status_code == 200

    record = Record.objects.get(external_id="rec-1")
    assert record.value == "120/80"
    assert record.visit.subject.site.study.external_id == "study-1"
