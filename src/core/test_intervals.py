import pytest
from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Form, Interval

@pytest.mark.django_db
def test_sync_intervals_idempotency_and_m2m():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    # Create forms to be linked
    form1 = Form.objects.create(imednet_id="f1", form_key="FK1", form_name="Form 1", study=study, revision=1)
    form2 = Form.objects.create(imednet_id="f2", form_key="FK2", form_name="Form 2", study=study, revision=1)

    data_list = [
        {
            "intervalId": "int1",
            "intervalName": "Interval 1",
            "intervalSequence": 1,
            "intervalGroupId": 10,
            "intervalGroupName": "Group A",
            "timeline": "Timeline A",
            "forms": [{"formId": "f1"}, {"formId": "f2"}]
        }
    ]

    # First sync: Create
    engine = StudySyncEngine()
    stats1 = engine.sync_intervals(study, data_list)

    assert stats1["created"] == 1
    assert stats1["updated"] == 0
    assert Interval.objects.count() == 1
    interval = Interval.objects.get(imednet_id="int1")
    assert interval.forms.count() == 2

    # Second sync: Update
    data_list[0]["intervalName"] = "Interval 1 Updated"
    data_list[0]["forms"] = [{"formId": "f1"}] # Remove one form

    stats2 = engine.sync_intervals(study, data_list)
    assert stats2["created"] == 0
    assert stats2["updated"] == 1
    interval.refresh_from_db()
    assert interval.interval_name == "Interval 1 Updated"
    assert interval.forms.count() == 1
    assert interval.forms.first().imednet_id == "f1"

@pytest.mark.django_db
def test_sync_intervals_partial_failure():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-456", name="Test Study 2", provider=provider)

    data_list = [
        {
            "intervalId": "int_ok",
            "intervalName": "Interval OK",
            "intervalSequence": 1,
            "intervalGroupId": 10,
            "intervalGroupName": "G",
            "timeline": "T",
        },
        {
            "intervalId": "int_fail",
            "intervalName": "Interval Fail",
            "intervalSequence": "invalid", # Should cause ValueError or TypeError
            "intervalGroupId": 10,
            "intervalGroupName": "G",
            "timeline": "T",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_intervals(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert Interval.objects.filter(imednet_id="int_ok").exists()
    assert not Interval.objects.filter(imednet_id="int_fail").exists()

@pytest.mark.django_db
def test_sync_intervals_soft_deletion():
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-soft", name="Soft Delete Study", provider=provider)

    data_list_1 = [
        {"intervalId": "i1", "intervalName": "I1", "intervalSequence": 1, "intervalGroupId": 1, "intervalGroupName": "G", "timeline": "T"},
        {"intervalId": "i2", "intervalName": "I2", "intervalSequence": 2, "intervalGroupId": 1, "intervalGroupName": "G", "timeline": "T"},
    ]
    engine = StudySyncEngine()
    engine.sync_intervals(study, data_list_1)
    assert Interval.objects.filter(study=study, disabled=False).count() == 2

    # i2 missing in next sync
    data_list_2 = [
        {"intervalId": "i1", "intervalName": "I1", "intervalSequence": 1, "intervalGroupId": 1, "intervalGroupName": "G", "timeline": "T"},
    ]
    stats = engine.sync_intervals(study, data_list_2)
    assert stats["soft_deleted"] == 1
    assert Interval.objects.get(imednet_id="i2").disabled is True
    assert Interval.objects.filter(study=study, disabled=False).count() == 1
