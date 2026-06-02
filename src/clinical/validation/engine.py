import logging
from typing import Dict, Any
from django.db import transaction
from clinical.models import ValidationRule, ValidationResult, Query, Record, Subject, SyncJob

logger = logging.getLogger(__name__)

def execute_validation_for_job(job_id: str):
    try:
        job = SyncJob.objects.get(id=job_id)
        rules = ValidationRule.objects.filter(is_active=True)
        for rule in rules:
            execute_rule_for_job(rule, job)
    except Exception as e:
        logger.error(f"Failed to execute validation for job {job_id}: {e}")

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
    
    # We'll just find all subjects and group them by name (or other match fields).
    # Since subjects don't have records attached to this rule directly, we'll just query Subjects.
    from collections import defaultdict
    subjects = Subject.objects.all()
    
    grouped = defaultdict(list)
    for sub in subjects:
        if sub.name:
            grouped[sub.name].append(sub)
            
    passed = True
    for name, subs in grouped.items():
        if len(subs) > 1:
            sites = {sub.site_id for sub in subs}
            if len(sites) > 1:
                # Duplicate across sites!
                passed = False
                
                # To create a query, we need a Record (Query model requires a Record). 
                # This is tricky because Subject isn't a Record.
                # However, the requirement says: "Validation failures correctly populate the internal Query table with the appropriate EDC reference keys."
                # Let's find a Record for these subjects (e.g., demographic record) or we just create a Query on the first available Record for the subject.
                for sub in subs:
                    record = Record.objects.filter(visit__subject=sub).first()
                    if record:
                        query = Query.objects.create(
                            record=record,
                            text=f"Global Duplicate Detection: Subject {sub.name} exists in multiple sites.",
                            status="OPEN",
                            sync_status="PENDING"
                        )
                        ValidationResult.objects.create(
                            rule=rule,
                            job=job,
                            passed=False,
                            error_message="Cross-site duplicate detected",
                            query=query
                        )
    if passed:
        ValidationResult.objects.create(rule=rule, job=job, passed=True)


def _check_compare_records(rule, job, dsl):
    # Example: {"check_type": "compare_records", "variable_1": "SYSBP", "variable_2": "DIABP", "operator": ">"}
    # Need to compare within the same visit?
    var1_name = dsl.get("variable_1")
    var2_name = dsl.get("variable_2")
    operator = dsl.get("operator")
    
    from clinical.models import Visit
    visits = Visit.objects.all()
    passed = True
    
    for visit in visits:
        rec1 = Record.objects.filter(visit=visit, variable__name=var1_name).first()
        rec2 = Record.objects.filter(visit=visit, variable__name=var2_name).first()
        
        if rec1 and rec2 and rec1.value and rec2.value:
            try:
                val1 = float(rec1.value)
                val2 = float(rec2.value)
                
                valid = True
                if operator == ">" and not (val1 > val2):
                    valid = False
                elif operator == "<" and not (val1 < val2):
                    valid = False
                elif operator == "==" and not (val1 == val2):
                    valid = False
                
                if not valid:
                    passed = False
                    query = Query.objects.create(
                        record=rec1,
                        text=f"Validation failed: {var1_name} ({val1}) should be {operator} {var2_name} ({val2})",
                        status="OPEN",
                        sync_status="PENDING"
                    )
                    ValidationResult.objects.create(
                        rule=rule,
                        job=job,
                        passed=False,
                        error_message="Field comparison failed",
                        query=query
                    )
            except ValueError:
                # Values aren't floats, skip or handle
                pass
                
    if passed:
        ValidationResult.objects.create(rule=rule, job=job, passed=True)
