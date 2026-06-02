import pytest
from django.contrib.auth import get_user_model

from clinical.management.commands.run_sync_worker import Command as WorkerCommand
from clinical.models import BufferedOrphan, Record, SyncJob
from users.jwt import create_jwt_token


def get_auth_headers():
    from clinical.models import Provider
    provider, _ = Provider.objects.get_or_create(name="Test Provider")
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="test_user", is_staff=True)
    token = create_jwt_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_STUDYKEY": "test-study", "HTTP_X_PROVIDER": str(provider.id)}


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
def test_reactive_orphan_buffering(client):
    headers = get_auth_headers()
    # Setup some base level 1 and 2
    client.post(
        "/api/clinical/studies",
        data={"externalId": "test-study", "name": "S1"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/sites",
        data={"externalId": "si-1", "studyExtId": "test-study", "name": "Si1"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/intervals",
        data={"externalId": "int-1", "studyExtId": "test-study", "name": "I1"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/forms",
        data={"externalId": "f-1", "studyExtId": "test-study", "name": "F1"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/variables",
        data={"externalId": "v-1", "formExtId": "f-1", "name": "V1"},
        content_type="application/json",
        **headers,
    )
    process_all_jobs()

    # Now sync a RECORD before the VISIT and SUBJECT
    # Visit doesn't exist, so this will orphan the record
    rec_resp = client.post(
        "/api/clinical/records",
        data={"externalId": "rec-orphan", "visitExtId": "vis-1", "variableExtId": "v-1", "value": "120/80"},
        content_type="application/json",
        **headers,
    )
    process_all_jobs()
    assert rec_resp.status_code == 200
    assert BufferedOrphan.objects.count() == 1

    # Sync VISIT before SUBJECT
    # Subject doesn't exist, so this will orphan the visit
    vis_resp = client.post(
        "/api/clinical/visits",
        data={"externalId": "vis-1", "subjectExtId": "sub-1", "intervalExtId": "int-1"},
        content_type="application/json",
        **headers,
    )
    process_all_jobs()
    assert vis_resp.status_code == 200
    assert BufferedOrphan.objects.count() == 2

    # Now sync the SUBJECT
    # This should trigger the visit, which should then trigger the record!
    sub_resp = client.post(
        "/api/clinical/subjects",
        data={"externalId": "sub-1", "siteExtId": "si-1", "name": "Sub1"},
        content_type="application/json",
        **headers,
    )
    process_all_jobs()
    assert sub_resp.status_code == 200

    # Check if all orphans are processed
    assert BufferedOrphan.objects.count() == 0

    # Check if the record is successfully created in DB
    record = Record.objects.filter(external_id="rec-orphan").first()
    assert record is not None
    assert record.value == "120/80"


@pytest.mark.django_db
def test_orphans_endpoint(client):
    headers = get_auth_headers()
    # This shouldn't do anything because we don't have orphans right now
    resp = client.get("/api/clinical/orphans", **headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
