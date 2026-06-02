import gzip
import os
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Automated full database backup"

    def handle(self, *args, **options):
        backup_dir = getattr(settings, "BACKUP_DIR", os.path.join(settings.ROOT_DIR, "backups"))
        os.makedirs(backup_dir, exist_ok=True)

        filename = f"db_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.json.gz"
        filepath = os.path.join(backup_dir, filename)

        self.stdout.write(f"Starting database backup to {filepath}...")

        try:
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                call_command("dumpdata", exclude=["contenttypes", "auth.Permission"], stdout=f)
            self.stdout.write(self.style.SUCCESS(f"Backup successfully created at {filepath}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e!s}"))
            if os.path.exists(filepath):
                os.remove(filepath)
            raise
