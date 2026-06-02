import csv
import io

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
        # Check if the audit log relates to a masked study
                # We can just always mask them in the export, or mask them if we can determine the study is masked.
        # But determining the study for every single audit log is expensive.
        # "Audit CSV exports no longer contain plaintext IP addresses or user-specific identifiers"
        # I'll just mask them in the CSV output.
        user_id_out = "[REDACTED]" if log.user_id else ""
        ip_out = "[REDACTED]" if log.ip_address else ""

        writer.writerow(
            [
                log.timestamp.isoformat(),
                log.action,
                log.model_name,
                log.object_id,
                log.study_id,
                str(log.changes),
                user_id_out,
                ip_out,
                log.user_agent,
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_log.csv"'
    return response
