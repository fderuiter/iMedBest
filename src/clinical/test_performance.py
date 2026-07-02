import pytest
from django.contrib.auth import get_user_model

from clinical.models import Provider, Site, Study, Subject
from users.jwt import create_jwt_token


@pytest.fixture
def auth_headers(db):
    provider, _ = Provider.objects.get_or_create(name="Test Provider")
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="test_user", is_staff=True)
    token = create_jwt_token(user)
    return {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_PROVIDER": str(provider.id),
        "HTTP_STUDYKEY": "test-study"
    }

@pytest.mark.django_db
def test_pagination_limits(client, auth_headers):
    # Create 150 subjects
    provider = Provider.objects.get(name="Test Provider")
    study = Study.objects.create(external_id="test-study", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="test-site", study=study, name="Test Site", provider=provider)

    subjects = [
        Subject(external_id=f"sub-{i}", site=site, name=f"Subject {i}", provider=provider)
        for i in range(150)
    ]
    Subject.objects.bulk_create(subjects)

    # Test default limit (25)
    resp = client.get("/api/v1/clinical/subjects", **auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 25
    assert data["count"] == 150

    # Test requested limit 50
    resp = client.get("/api/v1/clinical/subjects?limit=50", **auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 50

    # Test requested limit 1000 (should be capped at 100)
    resp = client.get("/api/v1/clinical/subjects?limit=1000", **auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 100

@pytest.mark.django_db
def test_n_plus_one_prevention(client, auth_headers, django_assert_max_num_queries):
    provider = Provider.objects.get(name="Test Provider")
    study = Study.objects.create(external_id="test-study", name="Test Study", provider=provider)
    site = Site.objects.create(external_id="test-site", study=study, name="Test Site", provider=provider)

    subjects = [
        Subject(external_id=f"sub-{i}", site=site, name=f"Subject {i}", provider=provider)
        for i in range(150)
    ]
    Subject.objects.bulk_create(subjects)

    # Query count should be constant regardless of limit
    with django_assert_max_num_queries(25):
        resp1 = client.get("/api/v1/clinical/subjects?limit=10", **auth_headers)
        assert resp1.status_code == 200

    with django_assert_max_num_queries(25):
        resp2 = client.get("/api/v1/clinical/subjects?limit=100", **auth_headers)
        assert resp2.status_code == 200

@pytest.mark.django_db
def test_subject_filters(client, auth_headers):
    provider = Provider.objects.get(name="Test Provider")
    study = Study.objects.create(external_id="test-study", name="Test Study", provider=provider)
    site1 = Site.objects.create(external_id="site-1", study=study, name="Site 1", provider=provider)
    site2 = Site.objects.create(external_id="site-2", study=study, name="Site 2", provider=provider)

    Subject.objects.create(external_id="s1", site=site1, name="S1", status="active", date_of_birth="1990-01-01", provider=provider)
    Subject.objects.create(external_id="s2", site=site2, name="S2", status="inactive", date_of_birth="1995-01-01", provider=provider)

    # Filter by site
    resp = client.get(f"/api/v1/clinical/subjects?siteId={site1.id}", **auth_headers)
    assert resp.json()["count"] == 1
    assert resp.json()["items"][0]["externalId"] == "s1"

    # Filter by status
    resp = client.get("/api/v1/clinical/subjects?status=inactive", **auth_headers)
    assert resp.json()["count"] == 1
    assert resp.json()["items"][0]["externalId"] == "s2"

    # Filter by DOB range
    resp = client.get("/api/v1/clinical/subjects?dobStart=1989-01-01&dobEnd=1991-01-01", **auth_headers)
    assert resp.json()["count"] == 1
    assert resp.json()["items"][0]["externalId"] == "s1"
