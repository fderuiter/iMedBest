from datetime import UTC, datetime

import pytest

from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from clinical.utils import parse_imednet_date_array
from core.models import User


@pytest.mark.django_db
def test_parse_imednet_date_array():
    # Valid date array
    date_array = [2026, 5, 13, 14, 6, 50, 612000000]
    expected = datetime(2026, 5, 13, 14, 6, 50, 612000, tzinfo=UTC)
    assert parse_imednet_date_array(date_array) == expected

    # Short date array
    date_array = [2026, 5, 13]
    expected = datetime(2026, 5, 13, 0, 0, 0, 0, tzinfo=UTC)
    assert parse_imednet_date_array(date_array) == expected

    # None input
    assert parse_imednet_date_array(None) is None

    # Invalid input
    assert parse_imednet_date_array("not a list") is None
    assert parse_imednet_date_array([2026, "invalid", 13]) is None


@pytest.mark.django_db
def test_sync_users():
    provider = Provider.objects.create(name="Test Provider")
    study = Study.objects.create(name="Test Study", external_id="study-1", provider=provider)

    data_list = [
        {
            "userId": "user-1",
            "login": "jdoe",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "userActiveInStudy": True,
            "roles": [{"roleName": "Investigator", "startDate": [2023, 1, 1], "endDate": [2025, 12, 31]}],
        }
    ]

    engine = StudySyncEngine()
    stats = engine.sync_users(study, data_list)

    assert stats["created"] == 1
    assert stats["failed"] == 0

    user = User.objects.get(imednet_id="user-1")
    assert user.login == "jdoe"
    assert user.first_name == "John"
    assert user.study == study

    assert user.roles.count() == 1
    role = user.roles.first()
    assert role.role_name == "Investigator"
    assert role.start_date == datetime(2023, 1, 1, tzinfo=UTC)

    # Test update
    data_list[0]["firstName"] = "Johnny"
    data_list[0]["roles"].append({"roleName": "Coordinator", "startDate": [2024, 1, 1]})

    stats = engine.sync_users(study, data_list)
    assert stats["updated"] == 1

    user.refresh_from_db()
    assert user.first_name == "Johnny"
    assert user.roles.count() == 2
    assert user.roles.filter(role_name="Coordinator").exists()
