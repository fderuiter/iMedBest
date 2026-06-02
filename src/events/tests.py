import pytest

from clinical.models import Form, Interval, Record, Site, Study, Subject, Variable, Visit
from events.models import DeliveryAttempt, OutboundEvent, Subscription
from events.tasks import process_delivery_attempt

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def test_subscription():
    return Subscription.objects.create(name="Test Sub", endpoint_url="http://mock.endpoint/webhook", event_type="")


@pytest.fixture
def mock_hierarchy():
    study = Study.objects.create(external_id="study1", name="Study 1")
    site = Site.objects.create(external_id="site1", name="Site 1", study=study)
    subject = Subject.objects.create(external_id="subj1", name="Subj 1", site=site)
    form = Form.objects.create(external_id="form1", name="Form 1", study=study)
    interval = Interval.objects.create(external_id="int1", name="Int 1", study=study)
    variable = Variable.objects.create(external_id="var1", name="Var 1", form=form)
    visit = Visit.objects.create(external_id="vis1", subject=subject, interval=interval)

    return study, site, subject, form, interval, variable, visit


def test_event_generation_and_batching(mock_hierarchy, test_subscription):
    _study, _site, _subject, _form, _interval, variable, visit = mock_hierarchy

    # We clear previous events
    OutboundEvent.objects.all().delete()
    DeliveryAttempt.objects.all().delete()

    # Create Record
    Record.objects.create(external_id="rec1", visit=visit, variable=variable, value="120/80")

    # Check if event was generated
    events = OutboundEvent.objects.filter(event_type="Record", action="CREATE")
    assert events.exists()
    event = events.first()

    # Check batching - should include Study, Site, Subject, Interval, Visit, Form, Variable, Record
    payload = event.payload
    types_in_batch = {item["type"] for item in payload}
    assert "Study" in types_in_batch
    assert "Subject" in types_in_batch
    assert "Visit" in types_in_batch
    assert "Record" in types_in_batch

    # Check parents appear BEFORE children
    types_list = [item["type"] for item in payload]
    study_idx = types_list.index("Study")
    record_idx = types_list.index("Record")
    assert study_idx < record_idx


from unittest.mock import patch


def test_background_worker(mock_hierarchy, test_subscription):
    _study, _site, _subject, _form, _interval, variable, visit = mock_hierarchy

    # Mock the celery delay so we can control when it runs
    with patch("events.tasks.process_delivery_attempt.delay"):
        # Create Record
        Record.objects.create(external_id="rec_worker", visit=visit, variable=variable, value="Worker test")

        attempt = DeliveryAttempt.objects.filter(event__event_type="Record").last()
        assert attempt.status == "PENDING"

        # Now run the task directly like a worker would
        process_delivery_attempt(attempt.id)

        attempt.refresh_from_db()
        assert attempt.status == "DELIVERED"


def test_subscription_filtering(mock_hierarchy):
    _study, _site, subject, _form, _interval, variable, visit = mock_hierarchy

    Subscription.objects.create(name="Only Records", endpoint_url="http://mock.endpoint/records", event_type="Record")

    DeliveryAttempt.objects.all().delete()
    OutboundEvent.objects.all().delete()

    # Updating Subject
    subject.name = "New Name"
    subject.save()

    # There should be an OutboundEvent for Subject
    assert OutboundEvent.objects.filter(event_type="Subject", action="UPDATE").exists()

    # But NO delivery attempt for the subscriber filtering for Record
    assert DeliveryAttempt.objects.count() == 0

    # Creating a Record
    Record.objects.create(external_id="rec_filter", visit=visit, variable=variable, value="Filter test")

    # NOW there should be a delivery attempt
    assert DeliveryAttempt.objects.count() == 1
