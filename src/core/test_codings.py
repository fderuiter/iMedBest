import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Coding, Form, Subject, User, Variable


@pytest.mark.django_db
class TestCodingSync:
    @pytest.fixture
    def setup_data(self):
        provider = Provider.objects.create(name="iMednet")
        study = Study.objects.create(name="Test Study", provider=provider, external_id="study1")
        subject = Subject.objects.create(study=study, imednet_id="1001", subject_key="S001", subject_status="Active")
        form = Form.objects.create(
            study=study, imednet_id="2001", form_key="F001", form_name="Form 1", form_type="Standard", revision=1
        )
        variable = Variable.objects.create(
            study=study,
            form=form,
            imednet_id="3001",
            variable_name="Var1",
            variable_oid="OID1",
            variable_type="Text",
            sequence=1,
            revision=1,
        )
        user = User.objects.create(
            study=study, imednet_id="4001", login="jdoe", first_name="John", last_name="Doe", email="jdoe@example.com"
        )
        return study, subject, form, variable, user

    def test_sync_codings_create(self, setup_data):
        study, subject, form, variable, user = setup_data

        coding_data = [
            {
                "codingId": 101,
                "siteName": "Site A",
                "siteId": 1,
                "subjectId": 1001,
                "subjectKey": "S001",
                "formId": 2001,
                "variableId": 3001,
                "variable": "Var1",
                "userId": 4001,
                "codedBy": "jdoe",
                "revision": 1,
                "recordId": 201,
                "value": "Adverse Event",
                "code": "AE001",
                "reason": "Initial coding",
                "dictionaryName": "MedDRA",
                "dictionaryVersion": "24.0",
                "dateCoded": [2023, 10, 27, 10, 0, 0, 0],
            }
        ]

        stats = StudySyncEngine.sync_codings(study, coding_data)

        assert stats["created"] == 1
        assert Coding.objects.count() == 1
        coding = Coding.objects.get(imednet_id="101")
        assert coding.code == "AE001"
        assert coding.subject == subject
        assert coding.form == form
        assert coding.variable_ref == variable
        assert coding.coded_by_user == user
        assert coding.subject_key_raw == "S001"
        assert coding.variable_raw == "Var1"
        assert coding.coded_by_raw == "jdoe"

    def test_sync_codings_idempotency(self, setup_data):
        study, _, _, _, _ = setup_data

        coding_data = [
            {
                "codingId": 101,
                "siteName": "Site A",
                "siteId": 1,
                "subjectId": 1001,
                "formId": 2001,
                "variableId": 3001,
                "userId": 4001,
                "revision": 1,
                "recordId": 201,
                "value": "Adverse Event",
                "code": "AE001",
                "dictionaryName": "MedDRA",
                "dictionaryVersion": "24.0",
                "dateCoded": [2023, 10, 27, 10, 0, 0, 0],
            }
        ]

        StudySyncEngine.sync_codings(study, coding_data)

        # Sync again with some changes
        coding_data[0]["code"] = "AE002"
        stats = StudySyncEngine.sync_codings(study, coding_data)

        assert stats["updated"] == 1
        assert Coding.objects.count() == 1
        assert Coding.objects.get(imednet_id="101").code == "AE002"

    def test_sync_codings_partial_failure(self, setup_data):
        study, _, _, _, _ = setup_data

        coding_data = [
            {
                "codingId": 101,
                "siteName": "Site A",
                "siteId": 1,
                "subjectId": 1001,
                "formId": 2001,
                "variableId": 3001,
                "userId": 4001,
                "revision": 1,
                "recordId": 201,
                "value": "AE 1",
                "code": "AE001",
                "dictionaryName": "MedDRA",
                "dictionaryVersion": "24.0",
                "dateCoded": [2023, 10, 27, 10, 0, 0, 0],
            },
            {
                "codingId": 102,
                "siteName": "Site A",
                "siteId": 1,
                "subjectId": 9999,
                "formId": 2001,
                "variableId": 3001,
                "userId": 4001,
                "revision": 1,
                "recordId": 202,
                "value": "AE 2",
                "code": "AE002",
                "dictionaryName": "MedDRA",
                "dictionaryVersion": "24.0",
                "dateCoded": [2023, 10, 27, 10, 0, 0, 0],
            },
        ]

        stats = StudySyncEngine.sync_codings(study, coding_data)

        assert stats["created"] == 1
        assert stats["failed"] == 1
        assert Coding.objects.count() == 1
        assert Coding.objects.filter(imednet_id="101").exists()
