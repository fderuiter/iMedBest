import pytest

from async_jobs.models import Job
from clinical import services
from clinical.api import (
    CodingSchemaIn,
    FormSchemaIn,
    IntervalSchemaIn,
    QuerySchemaIn,
    RecordRevisionSchemaIn,
    RecordSchemaIn,
    SiteSchemaIn,
    StudySchemaIn,
    SubjectSchemaIn,
    VariableSchemaIn,
    VisitSchemaIn,
)

from .models import Record


def process_jobs():
    schemas = {
        "sync_study": StudySchemaIn,
        "sync_site": SiteSchemaIn,
        "sync_subject": SubjectSchemaIn,
        "sync_form": FormSchemaIn,
        "sync_interval": IntervalSchemaIn,
        "sync_variable": VariableSchemaIn,
        "sync_visit": VisitSchemaIn,
        "sync_record": RecordSchemaIn,
        "sync_coding": CodingSchemaIn,
        "sync_query": QuerySchemaIn,
        "sync_revision": RecordRevisionSchemaIn,
    }
    endpoints = {
        "sync_study": services.sync_study,
        "sync_site": services.sync_site,
        "sync_subject": services.sync_subject,
        "sync_form": services.sync_form,
        "sync_interval": services.sync_interval,
        "sync_variable": services.sync_variable,
        "sync_visit": services.sync_visit,
        "sync_record": services.sync_record,
        "sync_coding": services.sync_coding,
        "sync_query": services.sync_query,
        "sync_revision": services.sync_revision,
    }
    for job in Job.objects.filter(status='Pending').order_by('created_at'):
        handler = endpoints[job.endpoint]
        schema_cls = schemas[job.endpoint]
        payload_obj = schema_cls(**job.payload)
        handler(payload_obj)
        job.status = 'Completed'
        job.save()

@pytest.mark.django_db
def test_multi_level_data_import(client):
    # Level 1
    study_resp = client.post(
        "/api/clinical/studies",
        data={"external_id": "study-1", "name": "Study 1"},
        content_type="application/json",
    )
    assert study_resp.status_code == 200

    site_resp = client.post(
        "/api/clinical/sites",
        data={"external_id": "site-1", "study_ext_id": "study-1", "name": "Site 1"},
        content_type="application/json",
    )
    assert site_resp.status_code == 200

    # Level 2
    subject_resp = client.post(
        "/api/clinical/subjects",
        data={"external_id": "sub-1", "site_ext_id": "site-1", "name": "Subject 1"},
        content_type="application/json",
    )
    assert subject_resp.status_code == 200

    form_resp = client.post(
        "/api/clinical/forms",
        data={"external_id": "form-1", "study_ext_id": "study-1", "name": "Form 1"},
        content_type="application/json",
    )
    assert form_resp.status_code == 200

    int_resp = client.post(
        "/api/clinical/intervals",
        data={"external_id": "int-1", "study_ext_id": "study-1", "name": "Interval 1"},
        content_type="application/json",
    )
    assert int_resp.status_code == 200

    # Level 3
    var_resp = client.post(
        "/api/clinical/variables",
        data={"external_id": "var-1", "form_ext_id": "form-1", "name": "Variable 1"},
        content_type="application/json",
    )
    assert var_resp.status_code == 200

    visit_resp = client.post(
        "/api/clinical/visits",
        data={"external_id": "visit-1", "subject_ext_id": "sub-1", "interval_ext_id": "int-1"},
        content_type="application/json",
    )
    assert visit_resp.status_code == 200

    # Level 4
    record_resp = client.post(
        "/api/clinical/records",
        data={"external_id": "rec-1", "visit_ext_id": "visit-1", "variable_ext_id": "var-1", "value": "120/80"},
        content_type="application/json",
    )
    assert record_resp.status_code == 200

    process_jobs()

    record = Record.objects.get(external_id="rec-1")
    assert record.value == "120/80"
    assert record.visit.subject.site.study.external_id == "study-1"
