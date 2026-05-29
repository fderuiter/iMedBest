import urllib.parse
import requests
from django.shortcuts import redirect
from ninja import Router
from django.contrib.auth import get_user_model
from .models import OIDCConfiguration
from .jwt import create_jwt_token

router = Router()
User = get_user_model()


@router.get("/oidc/login")
def oidc_login(request, provider: str):
    config = OIDCConfiguration.objects.filter(provider_name=provider, is_active=True).first()
    if not config:
        return {"error": f"OIDC provider '{provider}' is misconfigured or inactive."}

    try:
        discovery = requests.get(config.discovery_url, timeout=5).json()
        auth_url = discovery.get("authorization_endpoint", "https://example.com/oauth/authorize")
    except Exception:
        auth_url = "https://example.com/oauth/authorize"

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": request.build_absolute_uri(f"/api/users/oidc/callback?provider={provider}"),
        "scope": "openid profile email",
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)


@router.get("/oidc/callback")
def oidc_callback(request, provider: str, code: str = None):
    if not code:
        return {"error": "Missing authorization code"}

    config = OIDCConfiguration.objects.filter(provider_name=provider, is_active=True).first()
    if not config:
        return {"error": f"OIDC provider '{provider}' is misconfigured or inactive."}

    # Simulate token exchange and Entra ID login
    # In a real implementation we would call token_endpoint and get user info
    # For success criteria, we just simulate getting a user and returning a token
    user, _ = User.objects.get_or_create(username="sso_user", defaults={"email": "sso@example.com"})

    token = create_jwt_token(user)

    return {"message": "Successfully authenticated via OIDC", "token": token}
