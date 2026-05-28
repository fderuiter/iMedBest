from .base import *  # noqa: F403
from .base import ROOT_DIR, env

DEBUG = env("DEBUG", default=True)

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{(ROOT_DIR / 'db.sqlite3').as_posix()}"),
    "observability": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ROOT_DIR / "observability.sqlite3",
    }
}
