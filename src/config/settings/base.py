"""
Base Django settings for the iMedBest project.
"""

from pathlib import Path

import environ

ROOT_DIR = Path(__file__).resolve().parents[3]

env = environ.Env(
    ALLOWED_HOSTS=(list, []),
    DEBUG=(bool, False),
)
environ.Env.read_env(ROOT_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CLINICAL_API_KEY = env("CLINICAL_API_KEY", default=None)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_results",
    "core.apps.CoreConfig",
    "users.apps.UsersConfig",
    "clinical.apps.ClinicalConfig",
    "audit.apps.AuditConfig",
    "events.apps.EventsConfig",
    "django_auth_adfs",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "users.auth.CustomAdfsAuthCodeBackend",
]

# Microsoft Entra ID (OIDC) Settings
AUTH_ADFS = {
    "TENANT_ID": env("AZURE_TENANT_ID", default="00000000-0000-0000-0000-000000000000"),
    "CLIENT_ID": env("AZURE_CLIENT_ID", default="00000000-0000-0000-0000-000000000000"),
    "CLIENT_SECRET": env("AZURE_CLIENT_SECRET", default="django-insecure-dev-only-secret"),
    "RELYING_PARTY_ID": env("AZURE_CLIENT_ID", default="00000000-0000-0000-0000-000000000000"),
    "AUDIENCE": env("AZURE_CLIENT_ID", default="00000000-0000-0000-0000-000000000000"),
    "VERSION": "v2.0",
    "REDIR_URI": env("AZURE_CALLBACK_URL", default=None),
    "CREATE_NEW_USERS": True,
    "CLAIM_MAPPING": {
        "first_name": "given_name",
        "last_name": "family_name",
        "email": "email",
    },
    "USERNAME_CLAIM": "upn",
    "GROUPS_CLAIM": "groups",
    "MIRROR_GROUPS": True,
    "GROUP_TO_FLAG_MAPPING": {"is_staff": ["43063544-e34d-44a6-8025-a7b2169b60b7"]},
}

ADFS_GROUPS_MAPPING = {
    "762c26f0-6101-4475-b657-69c5e3170e5b": "Clinical_Admin",
    "d3269b61-29e2-4161-9c6a-48d5d4d38210": "Data_Analyst",
    "43063544-e34d-44a6-8025-a7b2169b60b7": "IT Manager",
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"

# Celery Settings
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "audit.middleware.AuditMiddleware",
    "clinical.api.StripSyncMetadataMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": ("django.contrib.auth.password_validation.UserAttributeSimilarityValidator"),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = ROOT_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

CELERY_BEAT_SCHEDULE = {
    "poll-edc-queries-every-minute": {
        "task": "clinical.tasks.poll_edc_queries",
        "schedule": 60.0,
    },
}

# Session Lifecycle Settings
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
