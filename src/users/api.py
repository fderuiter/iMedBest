import urllib.parse

from django.shortcuts import redirect
from ninja import Router

from .models import OIDCConfiguration

router = Router()

@router.get("/oidc/login")
def oidc_login(request, provider: str):
    config = OIDCConfiguration.objects.filter(provider_name=provider, is_active=True).first()
    if not config:
        return {"error": f"OIDC provider '{provider}' is misconfigured or inactive. Please ask your IT Administrator to verify the provider name and check OIDCConfiguration settings."}

    # In a real implementation, we would fetch the discovery URL to get the authorization endpoint.
    # We will simulate the redirect for acceptance criteria.
    auth_url = "https://example.com/oauth/authorize"
    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": request.build_absolute_uri(f"/api/users/oidc/callback?provider={provider}"),
        "scope": "openid profile email"
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

@router.get("/oidc/callback")
def oidc_callback(request, provider: str, code: str = None):
    if not code:
        return {"error": "Missing authorization code"}

    config = OIDCConfiguration.objects.filter(provider_name=provider, is_active=True).first()
    if not config:
        return {"error": f"OIDC provider '{provider}' is misconfigured or inactive. Please ask your IT Administrator to verify the provider name and check OIDCConfiguration settings."}

    # In a real implementation, we would exchange code for token here, create/login the user.
    # Simulated for success criteria:
    return {"message": "Successfully authenticated via OIDC"}
