import sys
from django.apps import AppConfig
from django.conf import settings


class ClinicalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "clinical"

    def ready(self):
        import os

        # Only run scheduler in the main process
        if os.environ.get("RUN_MAIN", None) != "true" and "runserver" in sys.argv:
            return

        # Do not run scheduler in test mode or migrate
        if "test" in sys.argv or "migrate" in sys.argv or "makemigrations" in sys.argv:
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from clinical.tasks import poll_imednet_high_priority

            scheduler = BackgroundScheduler()
            interval = getattr(settings, "IMEDNET_POLL_INTERVAL_SECONDS", 60)
            scheduler.add_job(
                poll_imednet_high_priority, "interval", seconds=interval, id="poll_imednet", replace_existing=True
            )
            scheduler.start()
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to start apscheduler: {e}")
