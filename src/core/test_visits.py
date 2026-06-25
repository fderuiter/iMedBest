import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Interval, Subject, Visit


@pytest.mark.django_db()
def test_sync_visits_idempotency():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-123", name="Test Study", provider=provider)

    subject = Subject.objects.create(imednet_id="subj1", subject_key="S001", study=study)
    interval = Interval.objects.create(
        imednet_id="int1", interval_name="Day 1", study=study, interval_sequence=1, interval_group_id=1
    )

    data_list = [
        {
            "visitId": "v1",
            "subjectKey": "S001",
            "intervalName": "Day 1",
            "startDate": "2024-01-01",
            "endDate": "2024-01-10",
            "visitDate": "2024-01-05",
            "deleted": False,
        }
    ]

    # First sync: Create
    engine = StudySyncEngine()
    stats1 = engine.sync_visits(study, data_list)

    assert stats1["created"] == 1
    assert stats1["updated"] == 0
    assert Visit.objects.count() == 1
    visit = Visit.objects.get(imednet_id="v1")
    assert visit.subject == subject
    assert visit.interval == interval
    assert str(visit.visit_date) == "2024-01-05"

    # Second sync: Update
    data_list[0]["visitDate"] = "2024-01-06"
    stats2 = engine.sync_visits(study, data_list)

    assert stats2["created"] == 0
    assert stats2["updated"] == 1
    visit.refresh_from_db()
    assert str(visit.visit_date) == "2024-01-06"


@pytest.mark.django_db()
def test_sync_visits_partial_failure():
    # Setup
    provider = Provider.objects.create(name="iMednet Provider")
    study = Study.objects.create(external_id="study-456", name="Test Study 2", provider=provider)

    Subject.objects.create(imednet_id="subj1", subject_key="S001", study=study)
    Interval.objects.create(
        imednet_id="int1", interval_name="Day 1", study=study, interval_sequence=1, interval_group_id=1
    )

    data_list = [
        {
            "visitId": "v_ok",
            "subjectKey": "S001",
            "intervalName": "Day 1",
            "visitDate": "2024-01-05",
        },
        {
            "visitId": "v_fail",
            "subjectKey": "NON_EXISTENT",
            "intervalName": "Day 1",
        },
    ]

    engine = StudySyncEngine()
    stats = engine.sync_visits(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert Visit.objects.filter(imednet_id="v_ok").exists()
    assert not Visit.objects.filter(imednet_id="v_fail").exists()
