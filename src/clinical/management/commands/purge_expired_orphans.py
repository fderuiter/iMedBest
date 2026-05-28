from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from clinical.models import BufferedOrphan
from django.conf import settings

class Command(BaseCommand):
    help = 'Purge expired buffered orphans'

    def handle(self, *args, **kwargs):
        ttl_days = getattr(settings, 'ORPHAN_BUFFER_TTL_DAYS', 30)
        cutoff_date = timezone.now() - timedelta(days=ttl_days)
        
        expired_orphans = BufferedOrphan.objects.filter(created_at__lt=cutoff_date)
        count = expired_orphans.count()
        
        expired_orphans.delete()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully purged {count} expired orphans'))
