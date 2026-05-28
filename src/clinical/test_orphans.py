from django.test import override_settings
import pytest
from clinical.models import Record, Subject, Visit, BufferedOrphan, Study, Site, Interval, Variable, Form

@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123")
def test_reactive_orphan_buffering(client):
    # Setup some base level 1 and 2
    client.post("/api/clinical/studies", data={"external_id": "st-1", "name": "S1"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/sites", data={"external_id": "si-1", "study_ext_id": "st-1", "name": "Si1"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/intervals", data={"external_id": "int-1", "study_ext_id": "st-1", "name": "I1"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/forms", data={"external_id": "f-1", "study_ext_id": "st-1", "name": "F1"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/variables", data={"external_id": "v-1", "form_ext_id": "f-1", "name": "V1"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    
    # Now sync a RECORD before the VISIT and SUBJECT
    # Visit doesn't exist, so this will orphan the record
    rec_resp = client.post(
        "/api/clinical/records",
        data={"external_id": "rec-orphan", "visit_ext_id": "vis-1", "variable_ext_id": "v-1", "value": "120/80"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert rec_resp.status_code == 202
    assert BufferedOrphan.objects.count() == 1
    
    # Sync VISIT before SUBJECT
    # Subject doesn't exist, so this will orphan the visit
    vis_resp = client.post(
        "/api/clinical/visits",
        data={"external_id": "vis-1", "subject_ext_id": "sub-1", "interval_ext_id": "int-1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert vis_resp.status_code == 202
    assert BufferedOrphan.objects.count() == 2
    
    # Now sync the SUBJECT
    # This should trigger the visit, which should then trigger the record!
    sub_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-1", "site_ext_id": "si-1", "name": "Sub1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert sub_resp.status_code == 200
    
    # Check if all orphans are processed
    assert BufferedOrphan.objects.count() == 0
    
    # Check if the record is successfully created in DB
    record = Record.objects.filter(external_id="rec-orphan").first()
    assert record is not None
    assert record.value == "120/80"
@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123")
def test_orphans_endpoint(client):
    # This shouldn't do anything because we don't have orphans right now
    resp = client.get("/api/clinical/orphans", HTTP_X_API_KEY="test_api_key_123")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
