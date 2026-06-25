from functools import lru_cache
from typing import Any

import jwt
import requests
from core.logging import get_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest
from django_auth_adfs.backend import AdfsAccessTokenBackend, AdfsAuthCodeBackend
from jwt import PyJWKClient
from ninja.security import HttpBearer

from .models import OIDCConfiguration

User = get_user_model()
logger = get_logger(__name__)


class CustomAdfsBackendMixin:
    def process_user_groups(self, claims, access_token):
        raw_groups = super().process_user_groups(claims, access_token)
        if not raw_groups:
            return []

        mapped_groups = []
        group_mapping = getattr(settings, "ADFS_GROUPS_MAPPING", {})

        for group in raw_groups:
            if group in group_mapping:
                mapped_groups.append(group_mapping[group])
            else:
                mapped_groups.append(group)
        return mapped_groups

    def update_user_flags(self, user, claims, claim_groups):
        adfs_settings = getattr(settings, "AUTH_ADFS", {})
        groups_claim = adfs_settings.get("GROUPS_CLAIM", "groups")

        raw_groups = claims.get(groups_claim, [])
        if not isinstance(raw_groups, list):
            raw_groups = [raw_groups]

        combined_groups = list(set(claim_groups) | set(raw_groups))
        super().update_user_flags(user, claims, combined_groups)

    def create_user(self, claims):
        username_claim = getattr(settings, "AUTH_ADFS", {}).get("USERNAME_CLAIM", "upn")
        username = claims.get(username_claim)
        if not username:
            return None

        with transaction.atomic():
            user, created = User.objects.select_for_update().get_or_create(
                username=username,
                defaults={
                    "email": claims.get("email", username),
                    "is_active": True,
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                logger.info("user_provisioned", username=username, source="EntraID")
            return user


@lru_cache(maxsize=10)
def get_jwks_uri(discovery_url):
    try:
        resp = requests.get(discovery_url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("jwks_uri")
    except Exception:  # noqa: S110
        pass
    return None


class OIDCBearer(HttpBearer):
    def __call__(self, request: HttpRequest) -> Any | None:
        result = super().__call__(request)
        if not result:
            from audit.models import AuditLog
            from audit.signals import get_client_ip

            ip_address = get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT")
            AuditLog.objects.create(
                action="SECURITY", model_name="ClinicalAPI", ip_address=ip_address, user_agent=user_agent
            )
        return result

    def authenticate(self, request, token):
        from django.contrib.auth import authenticate

        # Try Entra ID first via our custom access token backend
        try:
            user = authenticate(request, access_token=token)
        except Exception:
            user = None

        if user:
            request.user = user
            if hasattr(user, "groups"):
                request.user_roles = list(user.groups.values_list("name", flat=True))
            return token

        # Fallback to OIDC Providers (Dynamic/Multi-tenant OIDC)
        try:
            jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None

        configs = OIDCConfiguration.objects.filter(is_active=True)

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
                    options={"verify_issuer": False},
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

                request.user_roles = roles
                request.user = user
                return token
            except Exception:  # noqa: S112
                continue

        return None


class CustomAdfsAuthCodeBackend(CustomAdfsBackendMixin, AdfsAuthCodeBackend):
    pass


class CustomAdfsAccessTokenBackend(CustomAdfsBackendMixin, AdfsAccessTokenBackend):
    pass
