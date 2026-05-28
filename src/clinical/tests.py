import pytest

from .models import Subject


@pytest.mark.django_db
def test_multi_level_data_import(client):
    # Level 1
    study_resp = client.post(
        "/api/clinical/studies",
        data={"external_id": "study-1", "name": "Study 1"},
        content_type="application/json",
    )
    assert study_resp.status_code == 200

    site_resp = client.post(
        "/api/clinical/sites",
        data={"external_id": "site-1", "study_ext_id": "study-1", "name": "Site 1"},
        content_type="application/json",
    )
    assert site_resp.status_code == 200

    # Level 2
    subject_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-1", "site_ext_id": "site-1", "name": "Subject 1"},
        content_type="application/json",
    )
    assert subject_resp.status_code == 200

    subject = Subject.objects.get(external_id="sub-1")
    assert subject.name == "Subject 1"
    assert subject.site.study.external_id == "study-1"

    # Test invalid Study ID
    bad_site_resp = client.post(
        "/api/clinical/sites",
        data={"external_id": "site-invalid", "study_ext_id": "nonexistent-study", "name": "Site X"},
        content_type="application/json",
    )
    assert bad_site_resp.status_code == 404

    # Test invalid Site ID
    bad_subject_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-invalid", "site_ext_id": "nonexistent-site", "name": "Subject X"},
        content_type="application/json",
    )
    assert bad_subject_resp.status_code == 404
