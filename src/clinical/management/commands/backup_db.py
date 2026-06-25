import gzip
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from audit.utils import AdminContext
from clinical.storage import get_storage_adapter


class Command(BaseCommand):
    help = "Automated full database backup"

    def handle(self, *args, **options):
        filename = f"db_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.json.gz"
        # We save directly using storage_adapter, and place it in a 'backups' namespace
        # which will be relative to the adapter's root directory.

        self.stdout.write(f"Starting database backup to {filename}...")

        try:
            with AdminContext(), transaction.atomic():
                # Generate backup data
                from io import BytesIO, StringIO

                buf = StringIO()
                call_command("dumpdata", exclude=["contenttypes", "auth.Permission"], stdout=buf)

                compressed_buf = BytesIO()
                with gzip.GzipFile(fileobj=compressed_buf, mode="wb") as f:
                    f.write(buf.getvalue().encode("utf-8"))

                storage_adapter = get_storage_adapter()
                # We pass contains_phi=True explicitly because this is a database backup
                # which we assume contains PHI.
                storage_adapter.save(filename, compressed_buf.getvalue(), namespace="backups", contains_phi=True)
            self.stdout.write(self.style.SUCCESS(f"Backup successfully created at {filename}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e!s}"))
            raise
