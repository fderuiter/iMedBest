import logging

import requests
from django.conf import settings
from django.utils import timezone

from .models import Query, Record, SyncStatus, Variable, Visit

logger = logging.getLogger(__name__)


def poll_imednet_high_priority():
    api_url = getattr(settings, "IMEDNET_API_URL", "http://localhost:8080/imednet_mock")
    api_token = getattr(settings, "IMEDNET_API_TOKEN", "mock_token")

    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}

    status_obj, _ = SyncStatus.objects.get_or_create(id=1)
    status_obj.status = "POLLING"
    status_obj.save()

    try:
        # Fetch Queries
        query_resp = requests.get(f"{api_url}/high-priority/queries", headers=headers, timeout=10)
        if query_resp.status_code == 429:
            logger.warning("Rate limit reached for iMednet queries API")
        elif query_resp.status_code in {404, 204}:
            pass  # No data found
        else:
            query_resp.raise_for_status()
            queries_data = query_resp.json()
            if isinstance(queries_data, list):
                for q_data in queries_data:
                    # Map to existing clinical records via existing ingestion logic
                    record_ext_id = q_data.get("record_ext_id")
                    try:
                        record = Record.objects.get(external_id=record_ext_id)
                        Query.objects.update_or_create(
                            external_id=q_data.get("external_id"),
                            defaults={
                                "record": record,
                                "text": q_data.get("text"),
                                "clinical_timestamp": q_data.get("clinical_timestamp"),
                                "source_sequence": q_data.get("source_sequence"),
                            },
                        )
                    except Record.DoesNotExist:
                        logger.warning(f"Record {record_ext_id} not found for query {q_data.get('external_id')}")

        # Fetch Records
        record_resp = requests.get(f"{api_url}/high-priority/records", headers=headers, timeout=10)
        if record_resp.status_code == 429:
            logger.warning("Rate limit reached for iMednet records API")
        elif record_resp.status_code in {404, 204}:
            pass  # No data found
        else:
            record_resp.raise_for_status()
            records_data = record_resp.json()
            if isinstance(records_data, list):
                for r_data in records_data:
                    visit_ext_id = r_data.get("visit_ext_id")
                    var_ext_id = r_data.get("variable_ext_id")
                    try:
                        visit = Visit.objects.get(external_id=visit_ext_id)
                        variable = Variable.objects.get(external_id=var_ext_id)
                        Record.objects.update_or_create(
                            external_id=r_data.get("external_id"),
                            defaults={
                                "visit": visit,
                                "variable": variable,
                                "value": r_data.get("value"),
                                "clinical_timestamp": r_data.get("clinical_timestamp"),
                                "source_sequence": r_data.get("source_sequence"),
                            },
                        )
                    except (Visit.DoesNotExist, Variable.DoesNotExist):
                        logger.warning(f"Visit/Variable not found for record {r_data.get('external_id')}")

        status_obj.status = "SUCCESS"
        status_obj.last_successful_pull = timezone.now()
        status_obj.error_message = ""
        status_obj.save()

    except requests.exceptions.RequestException as e:
        status_obj.status = "ERROR"
        status_obj.error_message = str(e)
        status_obj.save()
        logger.error(f"Error polling iMednet: {e}")
