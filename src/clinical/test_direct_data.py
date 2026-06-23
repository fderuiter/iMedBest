import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from ninja.testing import TestClient

from clinical.api import router
from clinical.models import Provider, Subject, SyncJob
from clinical.storage import get_storage_adapter
from clinical.tasks import process_direct_data_job
from users.jwt import create_jwt_token

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_direct_data_bulk_ingestion():
    PASSWORD = "password"  # noqa: S105
    user = User.objects.create_user(username="testuser", email="test@example.com", password=PASSWORD, is_staff=True)
    provider = Provider.objects.create(name="Test Provider")

    token = create_jwt_token(user)
    headers = {"Authorization": f"Bearer {token}", "X-Provider": str(provider.id), "studyKey": "S1"}

    entities = [
        {"entity_type": "Study", "payload": {"external_id": "STUDY1", "name": "Test Study"}},
        {"entity_type": "Site", "payload": {"external_id": "SITE1", "study_ext_id": "STUDY1", "name": "Test Site"}},
    ]
    for i in range(2005):
        entities.append(
            {
                "entity_type": "Subject",
                "payload": {"external_id": f"SUB{i}", "site_ext_id": "SITE1", "metadata": {"some": "data"}},
            }
        )

    with patch("clinical.api.process_direct_data_job.delay"):
        client = TestClient(router)
        response = client.post("/sync-jobs", json={"entities": entities}, headers=headers)

    assert response.status_code == 200
    data = response.json()
    job_id = data["jobId"]

    job = SyncJob.objects.get(id=job_id)
    assert job.file_path is not None
    assert "sync_job_" in job.file_path

    # Verify metadata is stripped
    adapter = get_storage_adapter()
    with adapter.open(job.file_path, "rb", contains_phi=job.contains_phi) as f:
        data = json.loads(f.read().decode("utf-8"))
        for item in data:
            assert "metadata" not in item.get("payload", {})

    # Process the background job synchronously
    class MockRequest:
        user = job.user
        user_roles = []
        provider = job.provider
        META = {}

    with patch("audit.middleware.get_current_request", return_value=MockRequest()):
        process_direct_data_job(job.id)

    # Refresh job and verify status
    job.refresh_from_db()
    assert job.status == "COMPLETED", f"Job failed with error: {job.error_message}"

    # Verify persisted entities
    assert Subject.objects.filter(external_id__startswith="SUB").count() == 2005
    assert Subject.objects.filter(external_id="SUB0").exists()
