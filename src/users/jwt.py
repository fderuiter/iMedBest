import datetime

import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.contrib.auth import get_user_model
from users.models import OIDCConfiguration


def create_jwt_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_jwt_token(token):
    # Try our own token first
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_model = get_user_model()
        return user_model.objects.get(id=payload["user_id"])
    except jwt.PyJWTError:
        pass

    import requests

    # If it fails, try OIDC providers
    for config in OIDCConfiguration.objects.filter(is_active=True):
        try:
            discovery = requests.get(config.discovery_url, timeout=5).json()
            jwks_uri = discovery.get("jwks_uri")
            if not jwks_uri:
                continue

            jwks_client = PyJWKClient(jwks_uri)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=config.client_id,
            )

            email = payload.get("email") or payload.get("upn") or payload.get("preferred_username") or payload.get("unique_name")
            user_id = payload.get("oid") or payload.get("sub")

            if not email:
                email = f"{user_id}@oidc.user"

            user_model = get_user_model()
            user, _ = user_model.objects.get_or_create(username=user_id, defaults={"email": email, "is_staff": True})
            return user
        except Exception as e:
            continue

    return None
