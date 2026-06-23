import pytest

from clinical.models import Form as ClinicalForm
from clinical.models import Interval, Provider, Record, Site, Study, Subject, Variable, Visit
from clinical.services import StudySyncEngine
from core.models import RecordRevision, User


@pytest.mark.django_db
def test_sync_record_revisions_success():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="site-1", name="Site 1", study=study, provider=provider)
    subject = Subject.objects.create(external_id="1001", name="Subject 1001", site=site, provider=provider)
    interval = Interval.objects.create(external_id="int-1", name="Interval 1", study=study, provider=provider)
    visit = Visit.objects.create(external_id="visit-1", subject=subject, interval=interval, provider=provider)
    form = ClinicalForm.objects.create(external_id="form-1", name="Form 1", study=study, provider=provider)
    variable = Variable.objects.create(external_id="var-1", name="Var 1", form=form, provider=provider)
    record = Record.objects.create(external_id="5001", visit=visit, variable=variable, provider=provider)
    user = User.objects.create(imednet_id="user-1", login="jdoe", study=study)

    data_list = [
        {
            "recordRevisionId": "rev-1",
            "recordId": 5001,
            "recordOid": "REC_OID_1",
            "recordRevision": 1,
            "dataRevision": 1,
            "recordStatus": "Submitted",
            "subjectId": 1001,
            "subjectOid": "SUBJ_OID_1",
            "subjectKey": "S1001",
            "siteId": 1,
            "formKey": "FORM_1",
            "intervalId": 10,
            "role": "Data Entry",
            "user": "jdoe",
            "userId": "user-1",
            "reasonForChange": "Initial entry",
            "deleted": False,
        }
    ]

    engine = StudySyncEngine()
    stats = engine.sync_record_revisions(study, data_list)

    assert stats["created"] == 1
    assert RecordRevision.objects.count() == 1
    rev = RecordRevision.objects.get(imednet_id="rev-1")
    assert rev.record_status == "Submitted"
    assert rev.record == record
    assert rev.subject == subject
    assert rev.user_profile == user


@pytest.mark.django_db
def test_sync_record_revisions_idempotency():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="site-1", name="Site 1", study=study, provider=provider)
    subject = Subject.objects.create(external_id="1001", name="Subject 1001", site=site, provider=provider)
    interval = Interval.objects.create(external_id="int-1", name="Interval 1", study=study, provider=provider)
    visit = Visit.objects.create(external_id="visit-1", subject=subject, interval=interval, provider=provider)
    form = ClinicalForm.objects.create(external_id="form-1", name="Form 1", study=study, provider=provider)
    variable = Variable.objects.create(external_id="var-1", name="Var 1", form=form, provider=provider)
    Record.objects.create(external_id="5001", visit=visit, variable=variable, provider=provider)
    User.objects.create(imednet_id="user-1", login="jdoe", study=study)

    data_list = [
        {
            "recordRevisionId": "rev-1",
            "recordId": 5001,
            "recordOid": "REC_OID_1",
            "recordRevision": 1,
            "dataRevision": 1,
            "recordStatus": "Submitted",
            "subjectId": 1001,
            "subjectOid": "SUBJ_OID_1",
            "subjectKey": "S1001",
            "siteId": 1,
            "formKey": "FORM_1",
            "intervalId": 10,
            "role": "Data Entry",
            "user": "jdoe",
            "userId": "user-1",
            "reasonForChange": "Initial entry",
            "deleted": False,
        }
    ]

    engine = StudySyncEngine()
    engine.sync_record_revisions(study, data_list)

    # Sync again with updates
    data_list[0]["recordStatus"] = "Signed"
    stats2 = engine.sync_record_revisions(study, data_list)

    assert stats2["updated"] == 1
    assert RecordRevision.objects.count() == 1
    rev = RecordRevision.objects.get(imednet_id="rev-1")
    assert rev.record_status == "Signed"


@pytest.mark.django_db
def test_sync_record_revisions_partial_failure():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="site-1", name="Site 1", study=study, provider=provider)
    subject = Subject.objects.create(external_id="1001", name="Subject 1001", site=site, provider=provider)
    interval = Interval.objects.create(external_id="int-1", name="Interval 1", study=study, provider=provider)
    visit = Visit.objects.create(external_id="visit-1", subject=subject, interval=interval, provider=provider)
    form = ClinicalForm.objects.create(external_id="form-1", name="Form 1", study=study, provider=provider)
    variable = Variable.objects.create(external_id="var-1", name="Var 1", form=form, provider=provider)
    Record.objects.create(external_id="5001", visit=visit, variable=variable, provider=provider)
    User.objects.create(imednet_id="user-1", login="jdoe", study=study)

    data_list = [
        {
            "recordRevisionId": "rev-ok",
            "recordId": 5001,
            "recordOid": "OID_OK",
            "recordRevision": 1,
            "dataRevision": 1,
            "recordStatus": "OK",
            "subjectId": 1001,
            "subjectOid": "SUBJ_OID_1",
            "subjectKey": "S1001",
            "siteId": 1,
            "formKey": "FORM_1",
            "userId": "user-1",
        },
        {
            "recordRevisionId": "rev-fail",
            "recordId": 9999,  # Missing record
            "subjectId": 1001,
            "userId": "user-1",
            "recordStatus": "Fail",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_record_revisions(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert RecordRevision.objects.filter(imednet_id="rev-ok").exists()
    assert not RecordRevision.objects.filter(imednet_id="rev-fail").exists()
