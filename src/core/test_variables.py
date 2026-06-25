import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Form, Variable


@pytest.mark.django_db
def test_sync_variables_idempotency_and_form_lookup():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    # Create a form to be linked
    Form.objects.create(imednet_id="f1", form_key="FK1", form_name="Form 1", study=study, revision=1)

    data_list = [
        {
            "variableId": "v1",
            "formId": "f1",
            "variableType": "Text",
            "variableName": "Var 1",
            "sequence": 1,
            "revision": 1,
            "variableOid": "OID1",
            "label": "Label 1",
        }
    ]

    # First sync: Create
    engine = StudySyncEngine()
    stats1 = engine.sync_variables(study, data_list)

    assert stats1["created"] == 1
    assert stats1["updated"] == 0
    assert Variable.objects.count() == 1
    variable = Variable.objects.get(imednet_id="v1")
    assert variable.form.imednet_id == "f1"
    assert variable.variable_name == "Var 1"

    # Second sync: Update
    data_list[0]["variableName"] = "Var 1 Updated"

    stats2 = engine.sync_variables(study, data_list)
    assert stats2["created"] == 0
    assert stats2["updated"] == 1
    variable.refresh_from_db()
    assert variable.variable_name == "Var 1 Updated"


@pytest.mark.django_db
def test_sync_variables_partial_failure():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-456", name="Test Study 2", provider=provider)

    data_list = [
        {
            "variableId": "v_ok",
            "variableType": "Text",
            "variableName": "Var OK",
            "sequence": 1,
            "revision": 1,
            "variableOid": "OID_OK",
        },
        {
            "variableId": "v_fail",
            "variableType": "Text",
            "variableName": "Var Fail",
            "sequence": "invalid",  # Should cause ValueError or TypeError
            "revision": 1,
            "variableOid": "OID_FAIL",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_variables(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert Variable.objects.filter(imednet_id="v_ok").exists()
    assert not Variable.objects.filter(imednet_id="v_fail").exists()


@pytest.mark.django_db
def test_sync_variables_soft_deletion():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-soft", name="Soft Delete Study", provider=provider)

    data_list_1 = [
        {
            "variableId": "v1",
            "variableType": "Text",
            "variableName": "V1",
            "sequence": 1,
            "revision": 1,
            "variableOid": "OID1",
        },
        {
            "variableId": "v2",
            "variableType": "Text",
            "variableName": "V2",
            "sequence": 2,
            "revision": 1,
            "variableOid": "OID2",
        },
    ]
    engine = StudySyncEngine()
    engine.sync_variables(study, data_list_1)
    assert Variable.objects.filter(study=study, deleted=False).count() == 2

    # v2 missing in next sync
    data_list_2 = [
        {
            "variableId": "v1",
            "variableType": "Text",
            "variableName": "V1",
            "sequence": 1,
            "revision": 1,
            "variableOid": "OID1",
        },
    ]
    stats = engine.sync_variables(study, data_list_2)
    assert stats["soft_deleted"] == 1
    assert Variable.objects.get(imednet_id="v2").deleted is True
    assert Variable.objects.filter(study=study, deleted=False).count() == 1


@pytest.mark.django_db
def test_sync_variables_form_lookup_failure():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    data_list = [
        {
            "variableId": "v1",
            "formId": "non-existent-form",
            "variableType": "Text",
            "variableName": "Var 1",
            "sequence": 1,
            "revision": 1,
            "variableOid": "OID1",
        }
    ]

    engine = StudySyncEngine()
    stats = engine.sync_variables(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 0
    variable = Variable.objects.get(imednet_id="v1")
    assert variable.form is None
    assert variable.form_key_raw == "non-existent-form"
