import csv
import io
import zipfile

from django.db import models
from django.core.files.base import ContentFile
from django.http import HttpResponse

from .models import Record, Subject


def get_accessible_subjects(user):
    from users.models import SiteMembership, StudyMembership
    from django.db.models import Q
    if user.is_staff or user.is_superuser:
        return Subject.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role='clinical_auditor').values_list('study_id', flat=True)
    investigator_site_ids = SiteMembership.objects.filter(user=user, role='site_investigator').values_list('site_id', flat=True)
    return Subject.objects.filter(Q(site__study_id__in=auditor_study_ids) | Q(site_id__in=investigator_site_ids))


def get_accessible_records(user):
    from users.models import SiteMembership, StudyMembership
    from django.db.models import Q
    if user.is_staff or user.is_superuser:
        return Record.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role='clinical_auditor').values_list('study_id', flat=True)
    investigator_site_ids = SiteMembership.objects.filter(user=user, role='site_investigator').values_list('site_id', flat=True)
    return Record.objects.filter(Q(visit__subject__site__study_id__in=auditor_study_ids) | Q(visit__subject__site_id__in=investigator_site_ids))


def _generate_cdisc_export_file(job):
    zip_buffer = io.BytesIO()

    # Determine total subjects and records for progress updates
    user = job.user
    subjects_qs = get_accessible_subjects(user).select_related('site__study')
    records_qs = get_accessible_records(user).select_related('visit__subject__site__study', 'variable').order_by(
        models.F('source_sequence').asc(nulls_last=True),
        models.F('clinical_timestamp').asc(nulls_last=True),
        'created_at'
    )
    
    total_subjects = subjects_qs.count()
    total_records = records_qs.count()
    total_items = total_subjects + total_records
    if total_items == 0:
        total_items = 1 # avoid division by zero
    
    processed_items = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # DM Domain (Demographics)
        dm_buffer = io.StringIO()
        dm_writer = csv.writer(dm_buffer)
        dm_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC"])
        for subject in subjects_qs.iterator(chunk_size=2000):
            study_id = subject.site.study.external_id
            baseline_dt = subject.baseline_date
            rfstdtc = baseline_dt.isoformat() if baseline_dt else subject.created_at.isoformat()
            dm_writer.writerow([study_id, "DM", f"{study_id}-{subject.external_id}", subject.external_id, rfstdtc])
            
            processed_items += 1
            if processed_items % 1000 == 0:
                job.progress = int((processed_items / total_items) * 100)
                job.save(update_fields=['progress'])
                
        zip_file.writestr("DM.csv", dm_buffer.getvalue())

        # VS Domain (Vital Signs)
        vs_buffer = io.StringIO()
        vs_writer = csv.writer(vs_buffer)
        vs_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES"])
        
        for idx, record in enumerate(records_qs.iterator(chunk_size=5000)):
            study_id = record.visit.subject.site.study.external_id
            usubjid = f"{study_id}-{record.visit.subject.external_id}"
            seq = record.source_sequence if record.source_sequence is not None else idx + 1
            vs_writer.writerow([
                study_id,
                "VS",
                usubjid,
                seq,
                record.variable.external_id,
                record.variable.name,
                record.value
            ])
            
            processed_items += 1
            if processed_items % 1000 == 0:
                job.progress = int((processed_items / total_items) * 100)
                job.save(update_fields=['progress'])

        zip_file.writestr("VS.csv", vs_buffer.getvalue())

    zip_buffer.seek(0)
    job.file.save(f"cdisc_export_{job.id}.zip", ContentFile(zip_buffer.getvalue()), save=False)


def generate_cdisc_export(request):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # DM Domain (Demographics)
        dm_buffer = io.StringIO()
        dm_writer = csv.writer(dm_buffer)
        dm_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC"])
        for subject in get_accessible_subjects(request.user).select_related('site__study'):
            study_id = subject.site.study.external_id
            baseline_dt = subject.baseline_date
            rfstdtc = baseline_dt.isoformat() if baseline_dt else subject.created_at.isoformat()
            dm_writer.writerow([study_id, "DM", f"{study_id}-{subject.external_id}", subject.external_id, rfstdtc])
        zip_file.writestr("DM.csv", dm_buffer.getvalue())

        # VS Domain (Vital Signs)
        vs_buffer = io.StringIO()
        vs_writer = csv.writer(vs_buffer)
        vs_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES"])
        records = get_accessible_records(request.user).select_related('visit__subject__site__study', 'variable').order_by(
            models.F('source_sequence').asc(nulls_last=True),
            models.F('clinical_timestamp').asc(nulls_last=True),
            'created_at'
        )
        for idx, record in enumerate(records):
            study_id = record.visit.subject.site.study.external_id
            usubjid = f"{study_id}-{record.visit.subject.external_id}"
            seq = record.source_sequence if record.source_sequence is not None else idx + 1
            vs_writer.writerow([
                study_id,
                "VS",
                usubjid,
                seq,
                record.variable.external_id,
                record.variable.name,
                record.value
            ])
        zip_file.writestr("VS.csv", vs_buffer.getvalue())

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="cdisc_export.zip"'
    return response
