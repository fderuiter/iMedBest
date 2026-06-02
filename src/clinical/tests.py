import pytest
from django.contrib.auth import get_user_model

from clinical.management.commands.run_sync_worker import Command as WorkerCommand
from users.jwt import create_jwt_token

from .models import Record, SyncJob


def get_auth_headers(study_key="test-study"):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="test_user", is_staff=True)
    token = create_jwt_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_STUDYKEY": study_key}


def process_all_jobs():
    worker = WorkerCommand()
    while True:
        jobs = SyncJob.objects.filter(status__in=["PENDING", "PROCESSING"])
        processed = False
        for job in jobs:
            if worker.process_job(job):
                processed = True
        if not processed:
            break


@pytest.mark.django_db
def test_multi_level_data_import(client):
    headers = get_auth_headers("study-1")
    # Level 1
    study_resp = client.post(
        "/api/clinical/studies",
        data={"externalId": "study-1", "name": "Study 1"},
        content_type="application/json",
        **headers,
    )
    print(study_resp.json())  # noqa: T201
    assert study_resp.status_code == 202

    site_resp = client.post(
        "/api/clinical/sites",
        data={"externalId": "site-1", "studyExtId": "study-1", "name": "Site 1"},
        content_type="application/json",
        **headers,
    )
    assert site_resp.status_code == 202

    # Level 2
    subject_resp = client.post(
        "/api/clinical/subjects",
        data={"externalId": "sub-1", "siteExtId": "site-1", "name": "Subject 1"},
        content_type="application/json",
        **headers,
    )
    assert subject_resp.status_code == 202

    form_resp = client.post(
        "/api/clinical/forms",
        data={"externalId": "form-1", "studyExtId": "study-1", "name": "Form 1"},
        content_type="application/json",
        **headers,
    )
    assert form_resp.status_code == 202

    int_resp = client.post(
        "/api/clinical/intervals",
        data={"externalId": "int-1", "studyExtId": "study-1", "name": "Interval 1"},
        content_type="application/json",
        **headers,
    )
    assert int_resp.status_code == 202

    # Level 3
    var_resp = client.post(
        "/api/clinical/variables",
        data={"externalId": "var-1", "formExtId": "form-1", "name": "Variable 1"},
        content_type="application/json",
        **headers,
    )
    assert var_resp.status_code == 202

    visit_resp = client.post(
        "/api/clinical/visits",
        data={"externalId": "visit-1", "subjectExtId": "sub-1", "intervalExtId": "int-1"},
        content_type="application/json",
        **headers,
    )
    assert visit_resp.status_code == 202

    # Level 4
    record_resp = client.post(
        "/api/clinical/records",
        data={"externalId": "rec-1", "visitExtId": "visit-1", "variableExtId": "var-1", "value": "120/80"},
        content_type="application/json",
        **headers,
    )
    assert record_resp.status_code == 202

    process_all_jobs()

    record = Record.objects.get(external_id="rec-1")
    assert record.value == "120/80"
    assert record.visit.subject.site.study.external_id == "study-1"


@pytest.mark.django_db(transaction=True)
def test_longitudinal_reconstruction(client):
    headers = get_auth_headers("study-2")
    # Setup data
    client.post(
        "/api/clinical/studies",
        data={"externalId": "study-2", "name": "Study 2"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/sites",
        data={"externalId": "site-2", "studyExtId": "study-2", "name": "Site 2"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/subjects",
        data={"externalId": "sub-2", "siteExtId": "site-2", "name": "Subject 2"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/intervals",
        data={"externalId": "int-2", "studyExtId": "study-2", "name": "Interval 2"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/forms",
        data={"externalId": "form-2", "studyExtId": "study-2", "name": "Form 2"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/variables",
        data={"externalId": "var-2", "formExtId": "form-2", "name": "Variable 2"},
        content_type="application/json",
        **headers,
    )

    # Baseline visit
    client.post(
        "/api/clinical/visits",
        data={
            "externalId": "visit-base",
            "subjectExtId": "sub-2",
            "intervalExtId": "int-2",
            "clinicalTimestamp": "2024-01-01T10:00:00Z",
        },
        content_type="application/json",
        **headers,
    )

    # Record at Day 10
    client.post(
        "/api/clinical/records",
        data={
            "externalId": "rec-day10",
            "visitExtId": "visit-base",
            "variableExtId": "var-2",
            "value": "90",
            "clinicalTimestamp": "2024-01-11T10:00:00Z",
            "sourceSequence": 2,
        },
        content_type="application/json",
        **headers,
    )

    # Record at Day 5 (ingested out of order)
    client.post(
        "/api/clinical/records",
        data={
            "externalId": "rec-day5",
            "visitExtId": "visit-base",
            "variableExtId": "var-2",
            "value": "85",
            "clinicalTimestamp": "2024-01-06T10:00:00Z",
            "sourceSequence": 1,
        },
        content_type="application/json",
        **headers,
    )

    process_all_jobs()

    # Check offsets
    rec_day10 = Record.objects.get(external_id="rec-day10")
    assert rec_day10.offset_days == 10

    rec_day5 = Record.objects.get(external_id="rec-day5")
    assert rec_day5.offset_days == 5

    # Check export order (source sequence priorities)
    resp = client.get("/api/clinical/export/cdisc", **headers)
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    resp_dl = client.get(f"/api/clinical/export/cdisc/{job_id}/download", **headers)
    if resp_dl.status_code != 200:
        from clinical.models import ExportJob

        job = ExportJob.objects.get(id=job_id)
        print("FAILED JOB:", job.status, job.error_message)  # noqa: T201
    assert resp_dl.status_code == 200

    import io
    import zipfile
    from xml.etree import ElementTree

    z = zipfile.ZipFile(io.BytesIO(resp_dl.content))
    xml_data = z.read("cdisc_export.xml").decode("utf-8")
    root = ElementTree.fromstring(xml_data)  # noqa: S314

    ns = {"odm": "http://www.cdisc.org/ns/odm/v1.3"}
    item_datas = root.findall(".//odm:ItemData", ns)

    # We expect the ordering to match the source_sequence: rec-day5 then rec-day10
    values = [item.get("Value") for item in item_datas if item.get("ItemOID") == "var-2"]
    assert values == ["85", "90"]


@pytest.mark.django_db
def test_sync_job_endpoint(client):
    headers = get_auth_headers("study-async")
    from clinical.models import SyncJob

    payload = {
        "entities": [
            {
                "entityType": "Study",
                "hierarchyLevel": 1,
                "payload": {"externalId": "study-async", "name": "Async Study"},
            },
            {
                "entityType": "Site",
                "hierarchyLevel": 1,
                "payload": {"externalId": "site-async", "studyExtId": "study-async", "name": "Async Site"},
            },
        ]
    }

    resp = client.post("/api/clinical/sync-jobs", data=payload, content_type="application/json", **headers)
    assert resp.status_code == 202
    data = resp.json()
    assert "jobId" in data

    job_id = data["jobId"]
    job = SyncJob.objects.get(id=job_id)
    if job.status == "FAILED":
        print("JOB FAILED WITH ERROR:", job.error_message)  # noqa: T201
        for task in job.tasks.all():
            if task.status == "FAILED":
                print(f"TASK {task.id} FAILED WITH ERROR:", task.error_message)  # noqa: T201
    assert job.status in {"PENDING", "COMPLETED"}
    assert job.tasks.count() == 2


@pytest.mark.django_db
def test_sync_job_granular_failure(client):
    headers = get_auth_headers("study-atomic")

    # We will send a valid study and an invalid entity type
    payload = {
        "entities": [
            {
                "entityType": "Study",
                "hierarchyLevel": 1,
                "payload": {"externalId": "study-atomic", "name": "Atomic Study"},
            },
            {"entityType": "UnknownEntity", "hierarchyLevel": 1, "payload": {"externalId": "site-atomic"}},
        ]
    }

    resp = client.post("/api/clinical/sync-jobs", data=payload, content_type="application/json", **headers)
    assert resp.status_code == 202

    process_all_jobs()

    # Verify granular commit: Study should BE created, even though UnknownEntity failed
    from clinical.models import Study
    assert Study.objects.filter(external_id="study-atomic").exists()

    from clinical.models import SyncJob
    job_id = resp.json()["jobId"]
    job = SyncJob.objects.get(id=job_id)
    assert job.status == "FAILED"  # Because one task failed
