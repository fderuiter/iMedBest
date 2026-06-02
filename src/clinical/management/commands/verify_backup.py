import gzip
import json
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate that a database backup file is non-corrupt and ready for restoration"

    def add_arguments(self, parser):
        parser.add_argument("filepath", type=str, help="Path to the backup file")

    def handle(self, *args, **options):
        filepath = options["filepath"]

        if not os.path.exists(filepath):
            raise CommandError(f"File not found: {filepath}") from None

        self.stdout.write(f"Validating backup file: {filepath}")

        try:
            if filepath.endswith(".gz"):
                with gzip.open(filepath, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("JSON root must be a list of objects")

            self.stdout.write(self.style.SUCCESS(f"Validation successful. Found {len(data)} records."))
        except Exception as e:
            raise CommandError(f"Validation failed: {e!s}") from e
