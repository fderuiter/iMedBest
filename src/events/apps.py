from django.apps import AppConfig
import threading
import sys

class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        import events.signals  # noqa
        
        # Start worker unless we are running management commands that shouldn't start background threads
        # like migrate, makemigrations, collectstatic, test etc.
        is_management_command = False
        if len(sys.argv) > 1 and sys.argv[1] in [
            'migrate', 'makemigrations', 'collectstatic', 'shell', 
            'createsuperuser', 'test'
        ]:
            is_management_command = True
            
        # Also check for pytest or test execution
        if 'pytest' in sys.argv[0] or 'test' in sys.argv:
            # We don't start the worker in tests automatically to avoid side effects
            is_management_command = True

        if not is_management_command:
            from events.worker import start_worker
            start_worker()
