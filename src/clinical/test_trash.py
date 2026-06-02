import pytest
from django.contrib.auth import get_user_model

from users.jwt import create_jwt_token

from .models import Site, Study, Subject


def get_auth_headers():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="test_user", is_staff=True)
    token = create_jwt_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_STUDYKEY": "test-study"}


@pytest.mark.django_db()
def test_soft_delete_and_restore(client):
    headers = get_auth_headers()
    client.post(
        "/api/clinical/studies",
        data={"externalId": "test-study", "name": "Study Trash"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/sites",
        data={"externalId": "site-trash", "studyExtId": "test-study", "name": "Site Trash"},
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/clinical/subjects",
        data={"externalId": "sub-trash", "siteExtId": "site-trash", "name": "Subject Trash"},
        content_type="application/json",
        **headers,
    )

    from clinical.management.commands.run_sync_worker import Command as WorkerCommand

    from .models import SyncJob

    worker = WorkerCommand()
    for job in SyncJob.objects.all():
        worker.process_job(job)

    assert Study.objects.filter(external_id="test-study").count() == 1
    assert Site.objects.filter(external_id="site-trash").count() == 1

    # Delete study
    resp = client.delete("/api/clinical/studies/test-study", **headers)
    assert resp.status_code == 204

    assert Study.objects.filter(external_id="test-study").count() == 0
    assert Study.all_objects.filter(external_id="test-study", is_deleted=True).count() == 1

    # Children should be soft deleted
    assert Site.objects.filter(external_id="site-trash").count() == 0
    assert Site.all_objects.filter(external_id="site-trash", is_deleted=True).count() == 1
    assert Subject.objects.filter(external_id="sub-trash").count() == 0
    assert Subject.all_objects.filter(external_id="sub-trash", is_deleted=True).count() == 1

    # Restore study
    resp = client.post("/api/clinical/trash/Study/test-study/restore", **headers)
    assert resp.status_code == 200

    # Children should be restored
    assert Study.objects.filter(external_id="test-study").count() == 1
    assert Site.objects.filter(external_id="site-trash").count() == 1
    assert Subject.objects.filter(external_id="sub-trash").count() == 1
