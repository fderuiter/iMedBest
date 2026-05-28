import csv
import io
import zipfile

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
            dm_writer.writerow([study_id, "DM", f"{study_id}-{subject.external_id}", subject.external_id, subject.created_at.isoformat()])
        zip_file.writestr("DM.csv", dm_buffer.getvalue())

        # VS Domain (Vital Signs)
        vs_buffer = io.StringIO()
        vs_writer = csv.writer(vs_buffer)
        vs_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES"])
        for idx, record in enumerate(Record.objects.select_related('visit__subject__site__study', 'variable')):
            study_id = record.visit.subject.site.study.external_id
            usubjid = f"{study_id}-{record.visit.subject.external_id}"
            vs_writer.writerow([
                study_id,
                "VS",
                usubjid,
                idx + 1,
                record.variable.external_id,
                record.variable.name,
                record.value
            ])
        zip_file.writestr("VS.csv", vs_buffer.getvalue())

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="cdisc_export.zip"'
    return response
