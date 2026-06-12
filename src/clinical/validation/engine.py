import logging

from clinical.models import Query, Record, Subject, SyncJob, ValidationResult, ValidationRule

logger = logging.getLogger(__name__)


def execute_validation_for_job(job_id: str):
    try:
        job = SyncJob.objects.get(id=job_id)
        rules = ValidationRule.objects.filter(is_active=True)
        for rule in rules:
            execute_rule_for_job(rule, job)
    except Exception as e:
        logger.error(f"Failed to execute validation for job {job_id}: {e}")
        # Re-raise exception so Celery can mark the task as failed and trigger retries
        raise


def execute_rule_for_job(rule: ValidationRule, job: SyncJob):
    dsl = rule.rule_dsl
    check_type = dsl.get("check_type")

    if check_type == "cross_subject_duplicate":
        _check_cross_subject_duplicate(rule, job, dsl)
    elif check_type == "compare_records":
        _check_compare_records(rule, job, dsl)
    else:
        logger.warning(f"Unknown validation check_type: {check_type}")


def _check_cross_subject_duplicate(rule, job, dsl):
    # Cross-site duplicate detection
    # Example DSL: {"check_type": "cross_subject_duplicate", "match_fields": ["name"]}
    # If two subjects have the same name but different sites, flag both.

    # Scope subjects to the job's provider to avoid cross-tenant issues
    from collections import defaultdict

    provider_id = job.provider_id

    # Only check subjects within the job's provider scope, select_related to get site/study
    subjects = Subject.objects.filter(provider_id=provider_id).select_related("site", "site__study")

    # Group by (study_id or provider_id, name) instead of just name globally
    # This ensures we only flag duplicates within the same study/provider context
    grouped = defaultdict(list)
    for sub in subjects:
        if sub.name:
            # Use study_id if available, otherwise fall back to provider_id for grouping
            study_id = sub.site.study_id if sub.site and hasattr(sub.site, "study_id") and sub.site.study_id else None
            grouping_key = (study_id if study_id else provider_id, sub.name)
            grouped[grouping_key].append(sub)

    # Prefetch records for all subjects to avoid N+1 queries
    subject_ids = [sub.id for subs in grouped.values() for sub in subs if len(subs) > 1]
    if subject_ids:
        # Build a mapping of subject_id -> representative Record
        records_queryset = (
            Record.objects.filter(visit__subject_id__in=subject_ids)
            .select_related("visit", "visit__subject")
            .distinct()
        )

        subject_to_record = {}
        for record in records_queryset:
            if record.visit and record.visit.subject_id not in subject_to_record:
                subject_to_record[record.visit.subject_id] = record

    passed = True
    for (_context_id, _name), subs in grouped.items():
        if len(subs) > 1:
            sites = {sub.site_id for sub in subs}
            if len(sites) > 1:
                # Duplicate across sites!
                passed = False

                # Use the prefetched record mapping to avoid N+1
                for sub in subs:
                    record = subject_to_record.get(sub.id) if subject_ids else None

                    # Always create a ValidationResult even if no Record is found
                    if record:
                        # Check for existing OPEN query/validation result to avoid duplicates
                        existing_query = Query.objects.filter(
                            record=record, status="OPEN", text__contains=f"Subject {sub.name} exists in multiple sites"
                        ).first()

                        if not existing_query:
                            query = Query.objects.create(
                                record=record,
                                text=f"Global Duplicate Detection: Subject {sub.name} exists in multiple sites.",
                                status="OPEN",
                                sync_status="PENDING",
                            )
                        else:
                            query = existing_query

                        # Check for existing ValidationResult to avoid duplicates
                        existing_result = ValidationResult.objects.filter(rule=rule, job=job, query=query).first()

                        if not existing_result:
                            ValidationResult.objects.create(
                                rule=rule,
                                job=job,
                                passed=False,
                                error_message="Cross-site duplicate detected",
                                query=query,
                            )
                    else:
                        # No Record found - still create ValidationResult with query=None
                        existing_result = ValidationResult.objects.filter(
                            rule=rule,
                            job=job,
                            query__isnull=True,
                            error_message__contains=f"Subject {sub.name} cross-site duplicate (no record)",
                        ).first()

                        if not existing_result:
                            ValidationResult.objects.create(
                                rule=rule,
                                job=job,
                                passed=False,
                                error_message=(
                                    f"Cross-site duplicate detected: Subject {sub.name} (no backing Record available)"
                                ),
                                query=None,
                            )

    if passed and not ValidationResult.objects.filter(rule=rule, job=job, passed=True).exists():
        # Check if we already created a passed result for this rule+job
        ValidationResult.objects.create(rule=rule, job=job, passed=True)


def _check_compare_records(rule, job, dsl):
    # Need to compare within the same visit?
    var1_name = dsl.get("variable_1")
    var2_name = dsl.get("variable_2")
    operator = dsl.get("operator")

    from clinical.models import Visit

    # Restrict visits to the job's scope (provider-based filtering)
    # A more comprehensive approach would filter by job.study or job.site if available
    visits = Visit.objects.filter(subject__provider_id=job.provider_id)

    # Fetch all records for both variables in one query to avoid N+1
    records = Record.objects.filter(visit__in=visits, variable__name__in=[var1_name, var2_name]).select_related(
        "visit", "variable"
    )

    # Build a mapping of visit_id -> {var_name: Record}
    visit_records = {}
    for record in records:
        if record.visit_id not in visit_records:
            visit_records[record.visit_id] = {}
        if record.variable and record.variable.name:
            visit_records[record.visit_id][record.variable.name] = record

    passed = True

    for visit in visits:
        visit_data = visit_records.get(visit.id, {})
        rec1 = visit_data.get(var1_name)
        rec2 = visit_data.get(var2_name)

        if rec1 and rec2 and rec1.value and rec2.value:
            try:
                val1 = float(rec1.value)
                val2 = float(rec2.value)

                valid = True
                if operator == ">":
                    valid = val1 > val2
                elif operator == "<":
                    valid = val1 < val2
                elif operator == "==":
                    valid = val1 == val2
                else:
                    # Unsupported operator - mark as invalid and log warning
                    valid = False
                    logger.warning(
                        f"Unsupported operator '{operator}' in validation rule {rule.id} "
                        f"(rule: {rule.name}, var1: {var1_name}, var2: {var2_name})"
                    )

                if not valid:
                    passed = False
                    query = Query.objects.create(
                        record=rec1,
                        text=f"Validation failed: {var1_name} ({val1}) should be {operator} {var2_name} ({val2})",
                        status="OPEN",
                        sync_status="PENDING",
                    )
                    ValidationResult.objects.create(
                        rule=rule, job=job, passed=False, error_message="Field comparison failed", query=query
                    )
            except ValueError:
                # Values aren't floats, skip or handle
                pass

    if passed:
        ValidationResult.objects.create(rule=rule, job=job, passed=True)
