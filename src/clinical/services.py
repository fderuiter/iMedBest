from django.shortcuts import get_object_or_404

from .models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit


def sync_study(payload):
    study, _ = Study.objects.update_or_create(external_id=payload.external_id, defaults={"name": payload.name})
    return study

def sync_site(payload):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id, defaults={"study": study, "name": payload.name}
    )
    return site

def sync_subject(payload):
    site = get_object_or_404(Site, external_id=payload.site_ext_id)
    subject, _ = Subject.objects.update_or_create(
        external_id=payload.external_id, defaults={"site": site, "name": payload.name}
    )
    return subject

def sync_form(payload):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    form, _ = Form.objects.update_or_create(
        external_id=payload.external_id, defaults={"study": study, "name": payload.name}
    )
    return form

def sync_interval(payload):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    interval, _ = Interval.objects.update_or_create(
        external_id=payload.external_id, defaults={"study": study, "name": payload.name}
    )
    return interval

def sync_variable(payload):
    form = get_object_or_404(Form, external_id=payload.form_ext_id)
    variable, _ = Variable.objects.update_or_create(
        external_id=payload.external_id, defaults={"form": form, "name": payload.name}
    )
    return variable

def sync_visit(payload):
    subject = get_object_or_404(Subject, external_id=payload.subject_ext_id)
    interval = get_object_or_404(Interval, external_id=payload.interval_ext_id)
    visit, _ = Visit.objects.update_or_create(
        external_id=payload.external_id, defaults={"subject": subject, "interval": interval}
    )
    return visit

def sync_record(payload):
    visit = get_object_or_404(Visit, external_id=payload.visit_ext_id)
    variable = get_object_or_404(Variable, external_id=payload.variable_ext_id)
    record, _ = Record.objects.update_or_create(
        external_id=payload.external_id, defaults={"visit": visit, "variable": variable, "value": payload.value}
    )
    return record

def sync_coding(payload):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    coding, _ = Coding.objects.update_or_create(
        external_id=payload.external_id, defaults={"record": record, "code": payload.code}
    )
    return coding

def sync_query(payload):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    query, _ = Query.objects.update_or_create(
        external_id=payload.external_id, defaults={"record": record, "text": payload.text}
    )
    return query

def sync_revision(payload):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    revision, _ = RecordRevision.objects.update_or_create(
        external_id=payload.external_id, defaults={"record": record, "value": payload.value}
    )
    return revision
