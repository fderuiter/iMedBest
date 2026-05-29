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

        # VS Domain (Vital Signs)
        vs_buffer = io.StringIO()
        vs_writer = csv.writer(vs_buffer)
        vs_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES"])
        records = Record.objects.select_related('visit__subject__site__study', 'variable').order_by(
            'visit__subject__site__study__external_id',
            'visit__subject__external_id',
            models.F('source_sequence').asc(nulls_last=True),
            models.F('clinical_timestamp').asc(nulls_last=True),
            'created_at'
        )

        current_usubjid = None
        current_seq = 1

        for record in records:
            study_id = record.visit.subject.site.study.external_id
            usubjid = f"{study_id}-{record.visit.subject.external_id}"

            if usubjid != current_usubjid:
                current_usubjid = usubjid
                current_seq = 1

            seq = record.source_sequence if record.source_sequence is not None else current_seq
            if record.source_sequence is None:
                current_seq += 1

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
