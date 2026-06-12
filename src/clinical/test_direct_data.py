import pytest
from clinical.models import Provider, SyncJob
from django.contrib.auth import get_user_model
from users.jwt import create_jwt_token
from ninja.testing import TestClient
from clinical.api import router

User = get_user_model()

@pytest.mark.django_db(transaction=True)
def test_direct_data_bulk_ingestion():
    user = User.objects.create_user(username="testuser", email="test@example.com", password="password", is_staff=True)
    provider = Provider.objects.create(name="Test Provider", )
    
    token = create_jwt_token(user)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Provider": str(provider.id),
        "studyKey": "S1"
    }
    
    entities = []
    for i in range(2005):
        entities.append({
            "entity_type": "Subject",
            "payload": {
                "external_id": f"SUB{i}",
                "metadata": {"some": "data"}
            }
        })
        
    client = TestClient(router)
    response = client.post(
        "/sync-jobs",
        json={"entities": entities},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    job_id = data["jobId"]
    
    job = SyncJob.objects.get(id=job_id)
    assert job.file_path is not None
    assert "sync_job_" in job.file_path

    # Verify metadata is stripped
    import json
    from clinical.storage import get_storage_adapter
    adapter = get_storage_adapter()
    with adapter.open(job.file_path, "r") as f:
        data = json.load(f)
        for item in data:
            assert "metadata" not in item.get("payload", {})
