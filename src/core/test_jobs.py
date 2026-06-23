from unittest.mock import patch

import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Job


@pytest.mark.django_db
class TestJobSync:
    @pytest.fixture
    def setup_data(self):
        provider = Provider.objects.create(name="Test Provider")
        study = Study.objects.create(name="Test Study", provider=provider, external_id="STUDY-1")
        return study

    def test_sync_job_status_success(self, setup_data):
        study = setup_data
        batch_id = "BATCH-123"

        mock_payload = [
            {
                "jobId": "JOB-1",
                "batchId": batch_id,
                "state": "COMPLETED",
                "dateCreated": [2024, 1, 1, 12, 0, 0, 0],
                "dateStarted": [2024, 1, 1, 12, 5, 0, 0],
                "dateFinished": [2024, 1, 1, 12, 10, 0, 0],
            },
            {
                "jobId": "JOB-2",
                "batchId": batch_id,
                "state": "RUNNING",
                "dateCreated": [2024, 1, 1, 13, 0, 0, 0],
            },
        ]

        with patch.object(StudySyncEngine, "_fetch_job_payload", return_value=mock_payload):
            result = StudySyncEngine.sync_job_status(batch_id)

        assert "Created: 2" in result
        assert Job.objects.count() == 2

        job1 = Job.objects.get(imednet_id="JOB-1")
        assert job1.state == "COMPLETED"
        assert job1.batch_id == batch_id
        assert job1.study == study
        assert job1.date_created is not None
        assert job1.date_started is not None
        assert job1.date_finished is not None

        job2 = Job.objects.get(imednet_id="JOB-2")
        assert job2.state == "RUNNING"
        assert job2.date_finished is None

    def test_sync_job_status_partial_failure(self, setup_data):
        batch_id = "BATCH-ERR"

        mock_payload = [
            {
                "jobId": "JOB-GOOD",
                "batchId": batch_id,
                "state": "COMPLETED",
                "dateCreated": [2024, 1, 1, 12, 0, 0, 0],
            },
            {
                "jobId": None,  # Should cause failure
                "batchId": batch_id,
                "state": "BROKEN",
                "dateCreated": [2024, 1, 1, 12, 0, 0, 0],
            },
        ]

        with patch.object(StudySyncEngine, "_fetch_job_payload", return_value=mock_payload):
            result = StudySyncEngine.sync_job_status(batch_id)

        assert "Created: 1" in result
        assert "Failed: 1" in result
        assert Job.objects.count() == 1
        assert Job.objects.filter(imednet_id="JOB-GOOD").exists()

    def test_sync_job_status_idempotency(self, setup_data):
        batch_id = "BATCH-1"

        mock_payload = [
            {
                "jobId": "JOB-1",
                "batchId": batch_id,
                "state": "RUNNING",
                "dateCreated": [2024, 1, 1, 12, 0, 0, 0],
            }
        ]

        with patch.object(StudySyncEngine, "_fetch_job_payload", return_value=mock_payload):
            StudySyncEngine.sync_job_status(batch_id)

        assert Job.objects.count() == 1
        assert Job.objects.get(imednet_id="JOB-1").state == "RUNNING"

        # Update state in second sync
        mock_payload[0]["state"] = "COMPLETED"
        with patch.object(StudySyncEngine, "_fetch_job_payload", return_value=mock_payload):
            result = StudySyncEngine.sync_job_status(batch_id)

        assert "Updated: 1" in result
        assert Job.objects.count() == 1
        assert Job.objects.get(imednet_id="JOB-1").state == "COMPLETED"

    def test_sync_job_status_study_resolution(self, setup_data):
        provider = Provider.objects.create(name="Another Provider")
        other_study = Study.objects.create(name="Other Study", provider=provider, external_id="STUDY-2")
        batch_id = "BATCH-OTHER"

        # Pre-create a job for this batch with the other study
        Job.objects.create(
            study=other_study,
            imednet_id="JOB-EXISTING",
            batch_id=batch_id,
            state="RUNNING",
            date_created="2024-01-01T12:00:00Z",
        )

        mock_payload = [
            {
                "jobId": "JOB-EXISTING",
                "batchId": batch_id,
                "state": "COMPLETED",
                "dateCreated": [2024, 1, 1, 12, 0, 0, 0],
            }
        ]

        with patch.object(StudySyncEngine, "_fetch_job_payload", return_value=mock_payload):
            StudySyncEngine.sync_job_status(batch_id)

        job = Job.objects.get(imednet_id="JOB-EXISTING")
        assert job.study == other_study
        assert job.state == "COMPLETED"
