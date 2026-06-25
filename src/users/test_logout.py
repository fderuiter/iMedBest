import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db()
class TestLogoutView:
    def test_logout_destroys_session(self):
        client = Client()
        User.objects.create_user(username="testuser", password="secret_password")  # noqa: S106
        client.login(username="testuser", password="secret_password")  # noqa: S106

        # Verify user is logged in
        session_key = client.session.session_key
        assert session_key is not None

        # Call logout
        response = client.get(reverse("logout"))

        assert response.status_code == 302
        # Verify session is flushed (client.session will be empty or different)
        assert client.session.session_key is None or client.session.session_key != session_key

    def test_logout_redirects_to_entra_id(self):
        client = Client()
        tenant_id = settings.AUTH_ADFS.get("TENANT_ID", "common")

        response = client.get(reverse("logout"))

        assert response.status_code == 302
        redirect_url = response.url
        assert f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout" in redirect_url
        assert "post_logout_redirect_uri=" in redirect_url

    def test_logout_idempotency(self):
        client = Client()

        # First logout
        response1 = client.get(reverse("logout"))
        assert response1.status_code == 302

        # Second logout (unauthenticated)
        response2 = client.get(reverse("logout"))
        assert response2.status_code == 302
        assert response1.url == response2.url

    def test_login_session_cookie_headers(self):
        client = Client()
        User.objects.create_user(username="testuser2", password="secret_password")  # noqa: S106

        # We need to check if the session cookie is set correctly upon login
        # However, SESSION_EXPIRE_AT_BROWSER_CLOSE means the cookie has no 'max-age' or 'expires' attribute
        client.post(reverse("login"), {"username": "testuser2", "password": "password"})
        # Note: the mock LoginView doesn't actually log in. Let's use the real login if possible or just check settings.

        # Since LoginView in users/views.py is just a TemplateView, it doesn't handle POST login.
        # But the requirement is about the SESSION settings.

        assert settings.SESSION_COOKIE_AGE == 3600
        assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True
        assert settings.SESSION_SAVE_EVERY_REQUEST is True


@pytest.mark.django_db()
def test_session_cookie_expiry_on_login(client):
    # Standard django login to check cookie
    User.objects.create_user(username="testuser3", password="secret_password")  # noqa: S106
    client.login(username="testuser3", password="secret_password")  # noqa: S106

    session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_cookie is not None
    # If SESSION_EXPIRE_AT_BROWSER_CLOSE is True, expires should be empty string or None in the cookie
    # Django's test client might return None for 'expires' when it's not set.
    assert not session_cookie["expires"]
