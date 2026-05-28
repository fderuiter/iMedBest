from django.conf import settings
from django.test import SimpleTestCase


class TestLocalSettings(SimpleTestCase):
    def test_local_settings_default_to_sqlite(self):
        assert settings.AUTH_USER_MODEL == "users.User"
        assert settings.ASGI_APPLICATION == "config.asgi.application"
        assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
