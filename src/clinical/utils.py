from datetime import UTC, datetime


class MockRequest:
    def __init__(self, user, provider):
        self.user = user
        self.user_roles = ["cdisc"]
        self.provider = provider
        self.META = {}


def parse_imednet_date_array(date_array: list[int] | None) -> datetime | None:
    """
    Converts iMednet list date matrices (e.g. [2026, 5, 13, 14, 6, 50, 612000000])
    into UTC datetime objects.
    """
    if not date_array or not isinstance(date_array, list):
        return None

    try:
        # iMednet format: [year, month, day, hour, minute, second, nanoseconds]
        # Python datetime uses microseconds (nanoseconds / 1000)
        year = date_array[0]
        month = date_array[1]
        day = date_array[2]
        hour = date_array[3] if len(date_array) > 3 else 0
        minute = date_array[4] if len(date_array) > 4 else 0
        second = date_array[5] if len(date_array) > 5 else 0
        microsecond = date_array[6] // 1000 if len(date_array) > 6 else 0

        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=UTC)
    except (IndexError, ValueError, TypeError):
        return None
