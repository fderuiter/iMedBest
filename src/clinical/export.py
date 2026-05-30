import csv
import io
import zipfile

from django.db import models
from django.http import HttpResponse

from .models import Record, Subject


def generate_cdisc_export(request):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # DM Domain (Demographics)
        dm_buffer = io.StringIO()
        dm_writer = csv.writer(dm_buffer)
        dm_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC"])
        for subject in Subject.objects.select_related('site__study'):
            study_id = subject.site.study.external_id
            baseline_dt = subject.baseline_date
            rfstdtc = baseline_dt.isoformat() if baseline_dt else subject.created_at.isoformat()
            dm_writer.writerow([study_id, "DM", f"{study_id}-{subject.external_id}", subject.external_id, rfstdtc])
        zip_file.writestr("DM.csv", dm_buffer.getvalue())

        # Dynamic Domains
        records = Record.objects.select_related('visit__subject__site__study', 'variable').order_by(
            'variable__cdisc_domain',
            'visit__subject__site__study__external_id',
            'visit__subject__external_id',
            models.F('source_sequence').asc(nulls_last=True),
            models.F('clinical_timestamp').asc(nulls_last=True),
            'created_at'
        )

        domain_buffers = {}
        domain_writers = {}
        current_usubjid_per_domain = {}
        current_seq_per_domain = {}

        for record in records:
            domain = record.variable.cdisc_domain or "XX"
            if domain not in domain_buffers:
                domain_buffers[domain] = io.StringIO()
                writer = csv.writer(domain_buffers[domain])
                writer.writerow(["STUDYID", "DOMAIN", "USUBJID", f"{domain}SEQ", f"{domain}TESTCD", f"{domain}TEST", f"{domain}ORRES"])
                domain_writers[domain] = writer
                current_usubjid_per_domain[domain] = None
                current_seq_per_domain[domain] = 1
            
            study_id = record.visit.subject.site.study.external_id
            usubjid = f"{study_id}-{record.visit.subject.external_id}"

            if usubjid != current_usubjid_per_domain[domain]:
                current_usubjid_per_domain[domain] = usubjid
                current_seq_per_domain[domain] = 1

            seq = record.source_sequence if record.source_sequence is not None else current_seq_per_domain[domain]
            if record.source_sequence is None:
                current_seq_per_domain[domain] += 1

            domain_writers[domain].writerow([
                study_id,
                domain,
                usubjid,
                seq,
                record.variable.external_id,
                record.variable.name,
                record.value
            ])
            
        for domain, buffer in domain_buffers.items():
            zip_file.writestr(f"{domain}.csv", buffer.getvalue())

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="cdisc_export.zip"'
    return response
