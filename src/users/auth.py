from functools import lru_cache
from typing import Any

import jwt
import requests
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from jwt import PyJWKClient
from ninja.security import HttpBearer

from .models import OIDCConfiguration

User = get_user_model()

@lru_cache(maxsize=10)
def get_jwks_uri(discovery_url):
    try:
        resp = requests.get(discovery_url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("jwks_uri")
    except Exception:
        pass
    return None

class OIDCBearer(HttpBearer):
    def __call__(self, request: HttpRequest) -> Any | None:
        result = super().__call__(request)
        if not result:
            from audit.models import AuditLog
            from audit.signals import get_client_ip
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT')
            AuditLog.objects.create(
                action='SECURITY',
                model_name='ClinicalAPI',
                ip_address=ip_address,
                user_agent=user_agent
            )
        return result

    def authenticate(self, request, token):
        try:
            unverified_claims = jwt.decode(token, options={"verify_signature": False})
            audience = unverified_claims.get("aud")
            issuer = unverified_claims.get("iss")
        except Exception:
            return None

        configs = OIDCConfiguration.objects.filter(is_active=True)
        # If audience is an app ID, try matching

        valid_user = None
        user_roles = []
        for config in configs:
            jwks_uri = get_jwks_uri(config.discovery_url)
            if not jwks_uri:
                continue

            jwks_client = PyJWKClient(jwks_uri)
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                data = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=config.client_id,
                    options={"verify_issuer": False}
                )

                email = data.get("email") or data.get("preferred_username") or data.get("upn")
                if not email:
                    continue

                user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
                roles = data.get("roles", [])
                
                # Assign is_staff if "Admin" in roles
                is_admin = "Admin" in str(roles)
                if user.is_staff != is_admin:
                    user.is_staff = is_admin
                    user.save(update_fields=["is_staff"])

                if "Export" in str(roles) or "Extractor" in str(roles) or "CDISC" in str(roles) or getattr(user, 'is_staff', False):
                    # We might need to store roles if the check is done in the endpoint
                    pass

                request.user_roles = roles
                valid_user = user
                break
            except Exception:
                continue

        if valid_user:
            request.user = valid_user
            return token

        return None
