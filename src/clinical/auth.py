from ninja.security import HttpBearer
from .models import Provider
from users.auth import OIDCBearer

class MultiAuth(OIDCBearer):
    def authenticate(self, request, token):
        # 1. Try Provider API Key
        try:
            # Check if this token matches a Provider's API key
            providers = Provider.objects.filter(auth_type='API_KEY')
            for provider in providers:
                if provider.auth_credentials.get('api_key') == token:
                    request.provider = provider
                    return token
        except Exception:
            pass
        
        # 2. Try OIDC (existing)
        oidc_token = super().authenticate(request, token)
        if oidc_token:
            # If OIDC works, fall back to default provider if no explicit provider matches
            try:
                request.provider = Provider.objects.get(name='Legacy/Default')
            except Provider.DoesNotExist:
                request.provider = None
            return oidc_token
        
        return None
