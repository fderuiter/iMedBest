from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from clinical.models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit


class Command(BaseCommand):
    help = "Permanently purge soft-deleted items older than a configurable grace period (default 30 days)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30, help="Number of days after which deleted items are permanently purged"
        )

    def handle(self, *args, **options):
        days = options["days"]
        threshold_date = timezone.now() - timedelta(days=days)

        models_to_purge = [Study, Site, Subject, Form, Interval, Variable, Visit, Record, Coding, Query, RecordRevision]
        total_purged = 0

        # We need to purge from bottom to top of the hierarchy to avoid CASCADE deleting things that we want to count,
        # or we can just let CASCADE handle it and count. But Django's queryset.delete() returns the number of deleted items.  # noqa: E501
        # However, hard_delete() is custom method we added.

        for model_cls in reversed(models_to_purge):
            qs = model_cls.all_objects.filter(is_deleted=True, deleted_at__lt=threshold_date)
            count = qs.count()
            if count > 0:
                qs.hard_delete()
                self.stdout.write(self.style.SUCCESS(f"Purged {count} items from {model_cls.__name__}"))
                total_purged += count

        self.stdout.write(self.style.SUCCESS(f"Total items permanently purged: {total_purged}"))
