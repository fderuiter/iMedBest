from django.test import override_settings
import pytest

from .models import Record, Subject, Visit

@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123")
def test_multi_level_data_import(client):
    # Level 1
    study_resp = client.post(
        "/api/clinical/studies",
        data={"external_id": "study-1", "name": "Study 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert study_resp.status_code == 200

    site_resp = client.post(
        "/api/clinical/sites",
        data={"external_id": "site-1", "study_ext_id": "study-1", "name": "Site 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert site_resp.status_code == 200

    # Level 2
    subject_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-1", "site_ext_id": "site-1", "name": "Subject 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert subject_resp.status_code == 200

    form_resp = client.post(
        "/api/clinical/forms",
        data={"external_id": "form-1", "study_ext_id": "study-1", "name": "Form 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert form_resp.status_code == 200

    int_resp = client.post(
        "/api/clinical/intervals",
        data={"external_id": "int-1", "study_ext_id": "study-1", "name": "Interval 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert int_resp.status_code == 200

    # Level 3
    var_resp = client.post(
        "/api/clinical/variables",
        data={"external_id": "var-1", "form_ext_id": "form-1", "name": "Variable 1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert var_resp.status_code == 200

    visit_resp = client.post(
        "/api/clinical/visits",
        data={"external_id": "visit-1", "subject_ext_id": "sub-1", "interval_ext_id": "int-1"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert visit_resp.status_code == 200

    # Level 4
    record_resp = client.post(
        "/api/clinical/records",
        data={"external_id": "rec-1", "visit_ext_id": "visit-1", "variable_ext_id": "var-1", "value": "120/80"},
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123",
    )
    assert record_resp.status_code == 200

    record = Record.objects.get(external_id="rec-1")
    assert record.value == "120/80"
    assert record.visit.subject.site.study.external_id == "study-1"


@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123")
def test_longitudinal_reconstruction(client):
    # Setup data
    client.post("/api/clinical/studies", data={"external_id": "study-2", "name": "Study 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/sites", data={"external_id": "site-2", "study_ext_id": "study-2", "name": "Site 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/subjects", data={"external_id": "sub-2", "site_ext_id": "site-2", "name": "Subject 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/intervals", data={"external_id": "int-2", "study_ext_id": "study-2", "name": "Interval 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/forms", data={"external_id": "form-2", "study_ext_id": "study-2", "name": "Form 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/variables", data={"external_id": "var-2", "form_ext_id": "form-2", "name": "Variable 2"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    
    # Baseline visit
    client.post("/api/clinical/visits", data={
        "external_id": "visit-base", 
        "subject_ext_id": "sub-2", 
        "interval_ext_id": "int-2",
        "clinical_timestamp": "2024-01-01T10:00:00Z"
    }, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    
    # Record at Day 10
    client.post("/api/clinical/records", data={
        "external_id": "rec-day10", 
        "visit_ext_id": "visit-base", 
        "variable_ext_id": "var-2", 
        "value": "90",
        "clinical_timestamp": "2024-01-11T10:00:00Z",
        "source_sequence": 2
    }, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")

    # Record at Day 5 (ingested out of order)
    client.post("/api/clinical/records", data={
        "external_id": "rec-day5", 
        "visit_ext_id": "visit-base", 
        "variable_ext_id": "var-2", 
        "value": "85",
        "clinical_timestamp": "2024-01-06T10:00:00Z",
        "source_sequence": 1
    }, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    
    # Check offsets
    rec_day10 = Record.objects.get(external_id="rec-day10")
    assert rec_day10.offset_days == 10
    
    rec_day5 = Record.objects.get(external_id="rec-day5")
    assert rec_day5.offset_days == 5
    
    # Check export order (source sequence priorities)
    resp = client.get("/api/clinical/export/cdisc", HTTP_X_API_KEY="test_api_key_123")
    assert resp.status_code == 200
    
    import zipfile
    import io
    import csv
    
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    vs_csv = z.read("VS.csv").decode('utf-8').splitlines()
    reader = csv.DictReader(vs_csv)
    rows = list(reader)
    
    assert len(rows) == 2
    # Ensure ordered by source_sequence: rec-day5 then rec-day10
    assert rows[0]["VSORRES"] == "85"
    assert rows[0]["VSSEQ"] == "1"
    assert rows[1]["VSORRES"] == "90"
    assert rows[1]["VSSEQ"] == "2"

@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123", CELERY_TASK_ALWAYS_EAGER=True)
def test_sync_job_endpoint(client):
    from clinical.models import SyncJob
    
    payload = {
        "entities": [
            {
                "entity_type": "Study",
                "hierarchy_level": 1,
                "payload": {"external_id": "study-async", "name": "Async Study"}
            },
            {
                "entity_type": "Site",
                "hierarchy_level": 1,
                "payload": {"external_id": "site-async", "study_ext_id": "study-async", "name": "Async Site"}
            }
        ]
    }
    
    resp = client.post(
        "/api/clinical/sync-jobs",
        data=payload,
        content_type="application/json", HTTP_X_API_KEY="test_api_key_123"
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    
    job_id = data["job_id"]
    job = SyncJob.objects.get(id=job_id)
    if job.status == "FAILED":
        print("JOB FAILED WITH ERROR:", job.error_message)
        for task in job.tasks.all():
            if task.status == "FAILED":
                print(f"TASK {task.id} FAILED WITH ERROR:", task.error_message)
    assert job.status == "PENDING" or job.status == "COMPLETED"
    assert job.tasks.count() == 2
