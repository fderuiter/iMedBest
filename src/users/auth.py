from functools import lru_cache
from typing import Any

import jwt
import requests
import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest
from django_auth_adfs.backend import AdfsAccessTokenBackend, AdfsAuthCodeBackend
from django_auth_adfs.config import provider_config
from django_auth_adfs.rest_framework import AdfsAccessTokenAuthentication
from jwt import PyJWKClient
from ninja.security import HttpBearer

from .models import OIDCConfiguration

logger = structlog.get_logger(__name__)
User = get_user_model()


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
        try:
            unverified_claims = jwt.decode(token, options={"verify_signature": False})
            _ = unverified_claims.get("aud")
            _ = unverified_claims.get("iss")
        except Exception:
            return None

        configs = OIDCConfiguration.objects.filter(is_active=True)

        valid_user = None
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

                is_admin = "Admin" in str(roles)
                if user.is_staff != is_admin:
                    user.is_staff = is_admin
                    user.save(update_fields=["is_staff"])

                request.user_roles = roles
                valid_user = user
                break
            except Exception:  # noqa: S112
                continue

        if valid_user:
            request.user = valid_user
            return token

        return None


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

    def update_user_attributes(self, user, claims, claim_mapping=None):
        if claim_mapping is None:
            claim_mapping = getattr(settings, "AUTH_ADFS", {}).get("CLAIM_MAPPING", {})

        changed = False
        for field, claim in claim_mapping.items():
            if claim in claims:
                new_val = claims[claim]
                if getattr(user, field) != new_val:
                    setattr(user, field, new_val)
                    changed = True
        if changed:
            user.save(update_fields=list(claim_mapping.keys()))

    def update_user_groups(self, user, claim_groups):
        if getattr(settings, "AUTH_ADFS", {}).get("GROUPS_CLAIM") is not None:
            user_group_names = set(user.groups.all().values_list("name", flat=True))
            if set(claim_groups) != user_group_names:
                super().update_user_groups(user, claim_groups)


class CustomAdfsAuthCodeBackend(CustomAdfsBackendMixin, AdfsAuthCodeBackend):
    pass


class CustomAdfsAccessTokenBackend(CustomAdfsBackendMixin, AdfsAccessTokenBackend):
    def authenticate(self, request=None, access_token=None, **kwargs):
        provider_config.load_config()
        if access_token is None or access_token == "":
            return None

        if isinstance(access_token, bytes):
            access_token = access_token.decode()

        user = self.process_access_token(access_token)
        if user:
            return User.objects.select_related("profile").prefetch_related("groups").get(pk=user.pk)
        return None

    def create_user(self, claims):
        username_claim = getattr(settings, "AUTH_ADFS", {}).get("USERNAME_CLAIM", "upn")

        is_service_account = False
        if not claims.get(username_claim) and (claims.get("appid") or claims.get("idtyp") == "app"):
            is_service_account = True
            username = claims.get("oid") or claims.get("appid")
        else:
            username = claims.get(username_claim)

        if not username:
            raise PermissionDenied("User claim doesn't have the required username claim")

        with transaction.atomic():
            user, _ = User.objects.select_for_update().get_or_create(
                username=username, defaults={"is_service_account": is_service_account}
            )
            if not user.password:
                user.set_unusable_password()
                user.save(update_fields=["password"])
        return user


class AdfsJWTAuthentication(AdfsAccessTokenAuthentication):
    pass
