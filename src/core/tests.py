import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Form
from core.models import Subject as CoreSubject


@pytest.mark.django_db
def test_sync_forms_idempotency():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    data_list = [
        {
            "formId": "101",
            "formKey": "FORM_A",
            "formName": "Form A",
            "formType": "Normal",
            "revision": 1,
            "disabled": False,
        },
        {
            "formId": "102",
            "formKey": "FORM_B",
            "formName": "Form B",
            "formType": "Normal",
            "revision": 1,
            "disabled": False,
        },
    ]

    # First sync: Create
    engine = StudySyncEngine()
    stats1 = engine.sync_forms(study, data_list)

    assert stats1["created"] == 2
    assert stats1["updated"] == 0
    assert stats1["failed"] == 0
    assert Form.objects.count() == 2

    # Second sync: Update existing and add new
    data_list_2 = [
        {
            "formId": "101",  # Existing
            "formKey": "FORM_A",
            "formName": "Form A Updated",
            "formType": "Normal",
            "revision": 2,
            "disabled": False,
        },
        {
            "formId": "103",  # New
            "formKey": "FORM_C",
            "formName": "Form C",
            "formType": "Normal",
            "revision": 1,
            "disabled": False,
        },
    ]

    stats2 = engine.sync_forms(study, data_list_2)

    assert stats2["created"] == 1
    assert stats2["updated"] == 1
    assert stats2["failed"] == 0

    form_a = Form.objects.get(imednet_id="101")
    assert form_a.form_name == "Form A Updated"
    assert form_a.revision == 2
    assert Form.objects.count() == 3


@pytest.mark.django_db
def test_sync_forms_partial_failure():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-456", name="Test Study 2", provider=provider)

    data_list = [
        {
            "formId": "201",
            "formKey": "FORM_OK",
            "formName": "Form OK",
            "formType": "Normal",
            "revision": 1,
        },
        {
            "formId": "202",
            "formKey": None,
            "formName": "Form Fail",
            "formType": "Normal",
            "revision": "invalid",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_forms(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert Form.objects.filter(imednet_id="201").exists()
    assert not Form.objects.filter(imednet_id="202").exists()


@pytest.mark.django_db
def test_sync_forms_soft_deletion():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-soft", name="Soft Delete Study", provider=provider)

    # Initial sync
    data_list_1 = [
        {"formId": "301", "formKey": "F1", "formName": "Form 1", "formType": "T", "revision": 1},
        {"formId": "302", "formKey": "F2", "formName": "Form 2", "formType": "T", "revision": 1},
    ]
    engine = StudySyncEngine()
    engine.sync_forms(study, data_list_1)

    assert Form.objects.filter(study=study, disabled=False).count() == 2

    # Second sync: Form 302 is missing
    data_list_2 = [
        {"formId": "301", "formKey": "F1", "formName": "Form 1", "formType": "T", "revision": 1},
    ]
    stats = engine.sync_forms(study, data_list_2)

    assert stats["soft_deleted"] == 1
    assert Form.objects.get(imednet_id="302").disabled is True
    assert Form.objects.filter(study=study, disabled=False).count() == 1

    # Third sync: Form 302 is back
    data_list_3 = [
        {"formId": "301", "formKey": "F1", "formName": "Form 1", "formType": "T", "revision": 1},
        {"formId": "302", "formKey": "F2", "formName": "Form 2", "formType": "T", "revision": 1},
    ]
    engine.sync_forms(study, data_list_3)
    assert Form.objects.get(imednet_id="302").disabled is False


@pytest.mark.django_db
def test_sync_subjects_idempotency_and_keywords():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-subj", name="Subject Study", provider=provider)

    data_list = [
        {
            "subjectId": "501",
            "subjectOid": "OID_501",
            "subjectKey": "SUBJ_01",
            "subjectStatus": "Screening",
            "enrollmentStartDate": [2024, 1, 1, 10, 0, 0, 0],
            "keywords": ["tag1", "tag2"],
        }
    ]

    # First sync: Create
    engine = StudySyncEngine()
    stats1 = engine.sync_subjects(study, data_list)

    assert stats1["created"] == 1
    assert stats1["updated"] == 0
    assert stats1["failed"] == 0

    subject = CoreSubject.objects.get(imednet_id="501")
    assert subject.subject_key == "SUBJ_01"
    assert subject.keywords.count() == 2
    assert set(subject.keywords.values_list("keyword", flat=True)) == {"tag1", "tag2"}

    # Second sync: Update and change keywords
    data_list_2 = [
        {
            "subjectId": "501",
            "subjectOid": "OID_501",
            "subjectKey": "SUBJ_01",
            "subjectStatus": "Enrolled",
            "enrollmentStartDate": [2024, 1, 1, 10, 0, 0, 0],
            "keywords": ["tag2", "tag3"],
        }
    ]

    stats2 = engine.sync_subjects(study, data_list_2)
    assert stats2["created"] == 0
    assert stats2["updated"] == 1
    assert stats2["failed"] == 0
    subject.refresh_from_db()
    assert subject.subject_status == "Enrolled"
    assert subject.keywords.count() == 2
    assert set(subject.keywords.values_list("keyword", flat=True)) == {"tag2", "tag3"}


@pytest.mark.django_db
def test_sync_subjects_partial_failure():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-subj-fail", name="Subject Fail Study", provider=provider)

    data_list = [
        {
            "subjectId": "601",
            "subjectOid": "OID_601",
            "subjectKey": "SUBJ_OK",
            "subjectStatus": "Screening",
        },
        {
            "subjectId": "602",
            "subjectOid": "OID_602",
            "subjectKey": None,  # Should fail due to null subjectKey if unique or not null
            "subjectStatus": "Screening",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_subjects(study, data_list)

    assert stats["created"] == 1
    assert stats["updated"] == 0
    assert stats["failed"] == 1

    assert CoreSubject.objects.filter(imednet_id="601").exists()
    assert not CoreSubject.objects.filter(imednet_id="602").exists()
