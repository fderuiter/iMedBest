import os

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Restore an archived clinical entity and its hierarchy from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("filepath", type=str, help="Path to the JSON archive file")

    def handle(self, *args, **options):
        filepath = options["filepath"]

        if not os.path.exists(filepath):
            raise CommandError(f"File not found: {filepath}")

        self.stdout.write(f"Restoring archive from: {filepath}")

        try:
            with open(filepath, encoding="utf-8") as f:
                data = f.read()

            objects = list(serializers.deserialize("json", data))

            with transaction.atomic():
                for obj in objects:
                    obj.save()

            self.stdout.write(self.style.SUCCESS(f"Successfully restored {len(objects)} records."))
        except Exception as e:
            raise CommandError(f"Restore failed: {e!s}") from e
