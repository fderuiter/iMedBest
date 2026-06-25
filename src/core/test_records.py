import pytest

from clinical.models import Provider, Site, Study
from clinical.models import Subject as ClinicalSubject
from clinical.services import StudySyncEngine
from core.models import Form, Interval, Record, Variable
from core.models import Subject as CoreSubject


@pytest.mark.django_db
def test_sync_records_success():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="site-1", name="Site 1", study=study, provider=provider)

    # We need both Clinical and Core subjects because of the relationships
    ClinicalSubject.objects.create(external_id="1001", name="Subject 1001", site=site, provider=provider)
    CoreSubject.objects.create(imednet_id="1001", subject_key="S1001", study=study, site=site)

    Form.objects.create(imednet_id="form-1", form_key="FORM_1", form_name="Form 1", study=study, revision=1)
    Interval.objects.create(
        imednet_id="int-1",
        interval_name="Interval 1",
        study=study,
        interval_sequence=1,
        interval_group_id=1,
        timeline="Scheduled",
    )

    data_list = [
        {
            "recordId": "rec-1",
            "recordOid": "REC_OID_1",
            "recordType": "Standard",
            "recordStatus": "Submitted",
            "deleted": False,
            "subjectId": 1001,
            "subjectOid": "SUBJ_OID_1",
            "subjectKey": "S1001",
            "siteId": "site-1",
            "formId": "form-1",
            "intervalId": "int-1",
            "recordData": {"var1": "val1"},
            "keywords": ["tag1", "tag2"],
        }
    ]

    engine = StudySyncEngine()
    stats = engine.sync_records(study, data_list)

    assert stats["created"] == 1
    assert Record.objects.count() == 1
    record = Record.objects.get(imednet_id="rec-1")
    assert record.record_status == "Submitted"
    assert record.record_data == {"var1": "val1"}
    assert record.keywords.count() == 2
    assert set(record.keywords.values_list("keyword", flat=True)) == {"tag1", "tag2"}


@pytest.mark.django_db
def test_record_variable_validation_warning():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="site-1", name="Site 1", study=study, provider=provider)
    subject = CoreSubject.objects.create(imednet_id="1001", subject_key="S1001", study=study, site=site)
    form = Form.objects.create(imednet_id="form-1", form_key="FORM_1", form_name="Form 1", study=study, revision=1)
    interval = Interval.objects.create(
        imednet_id="int-1",
        interval_name="Interval 1",
        study=study,
        interval_sequence=1,
        interval_group_id=1,
        timeline="Scheduled",
    )

    # Define valid variables
    Variable.objects.create(
        study=study, form=form, imednet_id="v1", variable_name="known_var", sequence=1, revision=1, variable_oid="V1"
    )

    # This should trigger a warning in logs
    from structlog.testing import capture_logs

    with capture_logs() as caps:
        Record.objects.create(
            study=study,
            subject=subject,
            site=site,
            form=form,
            interval=interval,
            imednet_id="rec-2",
            record_status="Submitted",
            imednet_subject_id=1001,
            subject_key="S1001",
            record_data={"unknown_var": "some_value"},
        )

    assert any(log["event"] == "unknown_variable_in_record_data" for log in caps)
    assert any(log["variable_name"] == "unknown_var" for log in caps)


@pytest.mark.django_db
def test_submit_records_creates_job():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create(username="testuser", is_staff=True)

    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    engine = StudySyncEngine()
    result = engine.submit_records(study, [{"recordId": "new-rec"}], user=user)

    assert result["status"] == "success"
    from clinical.models import SyncJob

    assert SyncJob.objects.filter(id=result["jobId"]).exists()
