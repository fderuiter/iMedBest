import csv
import io
import hashlib

from django.http import HttpResponse, HttpResponseForbidden
from ninja import Router

from clinical.api import JWTBearer

from .models import AuditLog

router = Router(auth=[JWTBearer()])


@router.get("/export")
def export_audit_log(
    request,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: str | None = None,
    study_id: str | None = None,
):
    from users.models import StudyMembership

    is_admin = request.user.is_staff or request.user.is_superuser

    if not study_id:
        if not is_admin:
            return HttpResponseForbidden("A valid study_id is required to export audit logs.")
    elif not is_admin:
        has_role = StudyMembership.objects.filter(
            user=request.user, study_id=study_id, role__in=["clinical_auditor", "investigator"]
        ).exists()
        if not has_role:
            return HttpResponseForbidden("You do not have permission to export audit logs for this study.")

    qs = AuditLog.objects.all()

    if study_id:
        qs = qs.filter(study_id=study_id)
    if date_from:
        qs = qs.filter(timestamp__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__lte=date_to)
    if user_id:
        qs = qs.filter(user_id=user_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Timestamp", "Action", "Model", "Object ID", "Study ID", "Changes", "User ID", "IP Address", "User Agent"]
    )

    for log in qs:
        study_obj = log.study
        pii_masked = study_obj is not None and getattr(study_obj, "pii_masking_enabled", False)
        can_view_pii = request.user.is_staff or request.user.is_superuser or request.user.has_perm("users.view_pii")
        redact = pii_masked and not can_view_pii
        user_id_out = "[REDACTED]" if redact and log.user_id else (log.user_id or "")
        ip_out = "[REDACTED]" if redact and log.ip_address else (log.ip_address or "")

        writer.writerow(
            [
                log.timestamp.isoformat(),
                log.action,
                log.model_name,
                log.object_id,
                log.study_id or "",
                str(log.changes),
                user_id_out,
                ip_out,
                log.user_agent,
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_log.csv"'
    return response


@router.get("/reconciliation_report")
def reconciliation_report(request, study_id: str | None = None):
    from users.models import StudyMembership

    is_admin = request.user.is_staff or request.user.is_superuser

    if not study_id:
        if not is_admin:
            return HttpResponseForbidden("A valid study_id is required to export reconciliation report.")
    elif not is_admin:
        has_role = StudyMembership.objects.filter(
            user=request.user, study_id=study_id, role__in=["clinical_auditor", "investigator"]
        ).exists()
        if not has_role:
            return HttpResponseForbidden("You do not have permission to export reconciliation report for this study.")

    # Filter for entries that have an external_transaction_id
    qs = AuditLog.objects.exclude(external_transaction_id__isnull=True).exclude(external_transaction_id="")
    if study_id:
        qs = qs.filter(study_id=study_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Timestamp",
            "Action",
            "Model",
            "Object ID",
            "Changes",
            "Agent DID",
            "Supervisor DID",
            "External Transaction ID",
            "Cryptographic Signature",
            "Rejection Reason",
        ]
    )

    for log in qs:
        writer.writerow(
            [
                log.timestamp.isoformat(),
                log.action,
                log.model_name,
                log.object_id,
                str(log.changes),
                log.agent_did or "",
                log.supervisor_did or "",
                log.external_transaction_id or "",
                log.cryptographic_signature or "",
                log.rejection_reason or "",
            ]
        )

    csv_content = buffer.getvalue()
    content_hash = hashlib.sha256(csv_content.encode('utf-8')).hexdigest()
    
    final_content = csv_content + f"\n# SHA256 HASH: {content_hash}\n"
    
    response = HttpResponse(final_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reconciliation_report.csv"'
    response["X-Report-Hash"] = content_hash
    return response
