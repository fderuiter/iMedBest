import csv
import os
import tempfile
import zipfile

from django.db import models

from .models import Record, Subject


def create_cdisc_archive_file():
    # Create temporary files for the CSVs
    dm_temp = tempfile.NamedTemporaryFile(mode='w+', newline='', delete=False)
    vs_temp = tempfile.NamedTemporaryFile(mode='w+', newline='', delete=False)
    zip_temp = tempfile.NamedTemporaryFile(mode='w+b', delete=False)

    try:
        # DM Domain (Demographics)
        dm_writer = csv.writer(dm_temp)
        dm_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC"])

        # Batch fetching to reduce memory
        for subject in Subject.objects.select_related('site__study').iterator(chunk_size=1000):
            study_id = subject.site.study.external_id
            baseline_dt = subject.baseline_date
            rfstdtc = baseline_dt.isoformat() if baseline_dt else subject.created_at.isoformat()
            dm_writer.writerow([study_id, "DM", f"{study_id}-{subject.external_id}", subject.external_id, rfstdtc])

        dm_temp.close()

        # VS Domain (Vital Signs)
        vs_writer = csv.writer(vs_temp)
        vs_writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST", "VSORRES"])

        records = Record.objects.select_related('visit__subject__site__study', 'variable').order_by(
            models.F('source_sequence').asc(nulls_last=True),
            models.F('clinical_timestamp').asc(nulls_last=True),
            'created_at'
        )

        # Batch fetching
        for idx, record in enumerate(records.iterator(chunk_size=5000)):
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

        vs_temp.close()

        # Write to Zip
        with zipfile.ZipFile(zip_temp.name, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(dm_temp.name, "DM.csv")
            zip_file.write(vs_temp.name, "VS.csv")

    finally:
        # Cleanup CSV temp files
        if os.path.exists(dm_temp.name):
            os.remove(dm_temp.name)
        if os.path.exists(vs_temp.name):
            os.remove(vs_temp.name)

    return zip_temp.name


