import pytest
from django.test import override_settings
from .models import Study, Site, Subject

@pytest.mark.django_db
@override_settings(CLINICAL_API_KEY="test_api_key_123")
def test_soft_delete_and_restore(client):
    client.post("/api/clinical/studies", data={"external_id": "study-trash", "name": "Study Trash"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/sites", data={"external_id": "site-trash", "study_ext_id": "study-trash", "name": "Site Trash"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    client.post("/api/clinical/subjects", data={"external_id": "sub-trash", "site_ext_id": "site-trash", "name": "Subject Trash"}, content_type="application/json", HTTP_X_API_KEY="test_api_key_123")
    
    from clinical.management.commands.run_sync_worker import Command as WorkerCommand
    from .models import SyncJob
    worker = WorkerCommand()
    for job in SyncJob.objects.all():
        worker.process_job(job)

    assert Study.objects.filter(external_id="study-trash").count() == 1
    assert Site.objects.filter(external_id="site-trash").count() == 1
    
    # Delete study
    resp = client.delete("/api/clinical/studies/study-trash", HTTP_X_API_KEY="test_api_key_123")
    assert resp.status_code == 204
    
    assert Study.objects.filter(external_id="study-trash").count() == 0
    assert Study.all_objects.filter(external_id="study-trash", is_deleted=True).count() == 1
    
    # Children should be soft deleted
    assert Site.objects.filter(external_id="site-trash").count() == 0
    assert Site.all_objects.filter(external_id="site-trash", is_deleted=True).count() == 1
    assert Subject.objects.filter(external_id="sub-trash").count() == 0
    assert Subject.all_objects.filter(external_id="sub-trash", is_deleted=True).count() == 1
    
    # Restore study
    resp = client.post("/api/clinical/trash/Study/study-trash/restore", HTTP_X_API_KEY="test_api_key_123")
    assert resp.status_code == 200
    
    # Children should be restored
    assert Study.objects.filter(external_id="study-trash").count() == 1
    assert Site.objects.filter(external_id="site-trash").count() == 1
    assert Subject.objects.filter(external_id="sub-trash").count() == 1
