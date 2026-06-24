from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView, View


class LoginView(TemplateView):
    template_name = "users/login.html"


class LogoutView(View):
    """
    Custom LogoutView that flushes the local session and redirects to Microsoft Entra ID SLO.
    """

    def get(self, request):
        return self.handle_logout(request)

    def post(self, request):
        return self.handle_logout(request)

    def handle_logout(self, request):
        # 1. Flush the active session and expunge tokens
        # django.contrib.auth.logout(request) already performs request.session.flush()
        logout(request)

        # 2. Build the Microsoft Entra ID SLO redirect URL
        # Format: https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={homepage_url}
        auth_adfs = getattr(settings, "AUTH_ADFS", {})
        tenant_id = auth_adfs.get("TENANT_ID", "common")
        homepage_url = request.build_absolute_uri("/")

        slo_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={quote(homepage_url)}"
        )

        return HttpResponseRedirect(slo_url)
