import base64

from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet():
    key = settings.SECRET_KEY[:32].ljust(32, "a").encode("utf-8")
    encoded_key = base64.urlsafe_b64encode(key)
    return Fernet(encoded_key)


def encrypt(text: str) -> str:
    if not text:
        return text
    f = get_fernet()
    return f.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt(text: str) -> str:
    if not text:
        return text
    f = get_fernet()
    return f.decrypt(text.encode("utf-8")).decode("utf-8")
