from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.utils import AdminContext
from clinical.storage import get_storage_adapter


class Command(BaseCommand):
    help = "Restore an archived clinical entity and its hierarchy from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("filepath", type=str, help="Path to the JSON archive file")

    def handle(self, *args, **options):
        filepath = options["filepath"]

        storage_adapter = get_storage_adapter()

        if not storage_adapter.exists(filepath):
            raise CommandError(f"File not found: {filepath}")

        self.stdout.write(f"Restoring archive from: {filepath}")

        try:
            with AdminContext(), storage_adapter.open(filepath, "r", encoding="utf-8") as f:
                data = f.read()

                objects = list(serializers.deserialize("json", data))

                with transaction.atomic():
                    for obj in objects:
                        obj.save()

            self.stdout.write(self.style.SUCCESS(f"Successfully restored {len(objects)} records."))
        except Exception as e:
            raise CommandError(f"Restore failed: {e!s}") from e
