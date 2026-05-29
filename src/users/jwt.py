import datetime

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model


def create_jwt_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_jwt_token(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_model = get_user_model()
        return user_model.objects.get(id=payload["user_id"])
    except Exception:
        return None
