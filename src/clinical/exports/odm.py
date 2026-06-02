import os
import tempfile
import zipfile

from django.utils import timezone

from audit.models import AuditLog
from clinical.models import Form, Interval, Record, Site, Subject, Variable


def escape_xml(value):
    if value is None:
        return ""
    value = str(value)
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    value = value.replace("'", "&apos;")
    return value


def create_odm_xml(study, job):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8") as tmp:
        tmp.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tmp.write(
            f'<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3" FileType="Snapshot" Granularity="AllClinicalData" Archival="Yes" FileOID="EXPORT_{job.id}" CreationDateTime="{timezone.now().isoformat()}" ODMVersion="1.3.2" Originator="System" SourceSystem="Platform" SourceSystemVersion="1.0">\n'  # noqa: E501
        )

        study_oid = escape_xml(study.external_id)
        tmp.write(f'  <Study OID="{study_oid}">\n')
        tmp.write("    <GlobalVariables>\n")
        tmp.write(f"      <StudyName>{escape_xml(study.name)}</StudyName>\n")
        tmp.write(f"      <StudyDescription>{escape_xml(study.name)}</StudyDescription>\n")
        tmp.write(f"      <ProtocolName>{escape_xml(study.name)}</ProtocolName>\n")
        tmp.write("    </GlobalVariables>\n")

        tmp.write('    <MetaDataVersion OID="v1.0" Name="Initial Version">\n')
        tmp.write("      <Protocol>\n")
        intervals = Interval.objects.filter(study=study)
        for interval in intervals:
            tmp.write(
                f'        <StudyEventRef StudyEventOID="{escape_xml(interval.external_id)}" OrderNumber="1" Mandatory="Yes"/>\n'  # noqa: E501
            )
        tmp.write("      </Protocol>\n")

        for interval in intervals:
            tmp.write(
                f'      <StudyEventDef OID="{escape_xml(interval.external_id)}" Name="{escape_xml(interval.name)}" Repeating="No" Type="Scheduled">\n'  # noqa: E501
            )
            for form in Form.objects.filter(study=study):
                tmp.write(
                    f'        <FormRef FormOID="{escape_xml(form.external_id)}" OrderNumber="1" Mandatory="Yes"/>\n'
                )
            tmp.write("      </StudyEventDef>\n")

        for form in Form.objects.filter(study=study):
            tmp.write(
                f'      <FormDef OID="{escape_xml(form.external_id)}" Name="{escape_xml(form.name)}" Repeating="No">\n'
            )
            tmp.write(
                f'        <ItemGroupRef ItemGroupOID="IG_{escape_xml(form.external_id)}" OrderNumber="1" Mandatory="Yes"/>\n'  # noqa: E501
            )
            tmp.write("      </FormDef>\n")
            tmp.write(
                f'      <ItemGroupDef OID="IG_{escape_xml(form.external_id)}" Name="{escape_xml(form.name)} Group" Repeating="No">\n'  # noqa: E501
            )
            variables = Variable.objects.filter(form=form)
            for var in variables:
                tmp.write(
                    f'        <ItemRef ItemOID="{escape_xml(var.external_id)}" OrderNumber="1" Mandatory="Yes"/>\n'
                )
            tmp.write("      </ItemGroupDef>\n")
            for var in variables:
                tmp.write(
                    f'      <ItemDef OID="{escape_xml(var.external_id)}" Name="{escape_xml(var.name)}" DataType="text"/>\n'  # noqa: E501
                )

        tmp.write("    </MetaDataVersion>\n")
        tmp.write("  </Study>\n")

        tmp.write(f'  <AdminData StudyOID="{study_oid}">\n')
        for site in Site.objects.filter(study=study):
            tmp.write(
                f'    <Location OID="{escape_xml(site.external_id)}" Name="{escape_xml(site.name)}" LocationType="Site"/>\n'  # noqa: E501
            )

        # We will collect unique users while streaming ClinicalData to avoid memory issues,
        # but ODM requires AdminData before ClinicalData.
        # So we query distinct users from AuditLogs for this study's records.
        # Using a subquery might be slow, let's just query User directly if they have AuditLogs for this study
        # Actually, let's just dump all users involved in audit logs.
        # To be safe and fast, we can just iterate over all User objects and write them if they exist in logs,
        # but for now, let's just output a generic system user, or all users in DB since it's an internal platform.
        from users.models import User

        mask_pii = getattr(study, "pii_masking_enabled", False)
        for user in User.objects.all().iterator(chunk_size=1000):
            uid = f"MASKED_{user.id}" if mask_pii else str(user.id)
            uname = "MASKED" if mask_pii else user.username
            tmp.write(f'    <User OID="{uid}">\n')
            tmp.write(f"      <LoginName>{escape_xml(uname)}</LoginName>\n")
            tmp.write(f"      <DisplayName>{escape_xml(uname)}</DisplayName>\n")
            tmp.write("    </User>\n")
        tmp.write("  </AdminData>\n")

        tmp.write(f'  <ReferenceData StudyOID="{study_oid}" MetaDataVersionOID="v1.0"/>\n')

        tmp.write(f'  <ClinicalData StudyOID="{study_oid}" MetaDataVersionOID="v1.0">\n')
        subjects = Subject.objects.filter(site__study=study).prefetch_related("site").iterator(chunk_size=1000)
        for subject in subjects:
            tmp.write(f'    <SubjectData SubjectKey="{escape_xml(subject.external_id)}">\n')
            tmp.write(f'      <SiteRef LocationOID="{escape_xml(subject.site.external_id)}"/>\n')

            records = (
                Record.objects.filter(visit__subject=subject)
                .select_related("visit__interval", "variable__form")
                .order_by("source_sequence", "clinical_timestamp", "created_at")
                .iterator(chunk_size=1000)
            )

            curr_event = None
            curr_form = None
            curr_ig = None

            for rec in records:
                event_oid = rec.visit.interval.external_id
                form_oid = rec.variable.form.external_id
                ig_oid = f"IG_{form_oid}"

                if event_oid != curr_event:
                    if curr_ig:
                        tmp.write("          </ItemGroupData>\n")
                    if curr_form:
                        tmp.write("        </FormData>\n")
                    if curr_event:
                        tmp.write("      </StudyEventData>\n")
                    tmp.write(f'      <StudyEventData StudyEventOID="{escape_xml(event_oid)}">\n')
                    curr_event = event_oid
                    curr_form = None
                    curr_ig = None

                if form_oid != curr_form:
                    if curr_ig:
                        tmp.write("          </ItemGroupData>\n")
                    if curr_form:
                        tmp.write("        </FormData>\n")
                    tmp.write(f'        <FormData FormOID="{escape_xml(form_oid)}">\n')
                    curr_form = form_oid
                    curr_ig = None

                if ig_oid != curr_ig:
                    if curr_ig:
                        tmp.write("          </ItemGroupData>\n")
                    tmp.write(f'          <ItemGroupData ItemGroupOID="{escape_xml(ig_oid)}">\n')
                    curr_ig = ig_oid

                tmp.write(
                    f'            <ItemData ItemOID="{escape_xml(rec.variable.external_id)}" Value="{escape_xml(rec.value)}">\n'  # noqa: E501
                )

                logs = AuditLog.objects.filter(model_name="Record", object_id=str(rec.external_id)).order_by(
                    "timestamp"
                )
                for log in logs:
                    tmp.write("              <AuditRecord>\n")
                    user_oid = "System"
                    if log.user:
                        user_oid = f"MASKED_{log.user.id}" if mask_pii else str(log.user.id)
                    tmp.write(f'                <UserRef UserOID="{escape_xml(user_oid)}"/>\n')
                    tmp.write(f'                <LocationRef LocationOID="{escape_xml(subject.site.external_id)}"/>\n')
                    tmp.write(f"                <DateTimeStamp>{log.timestamp.isoformat()}</DateTimeStamp>\n")
                    tmp.write(f"                <ReasonForChange>{escape_xml(log.action)}</ReasonForChange>\n")
                    tmp.write(f"                <SourceID>{log.id}</SourceID>\n")
                    tmp.write("              </AuditRecord>\n")

                tmp.write("            </ItemData>\n")

            if curr_ig:
                tmp.write("          </ItemGroupData>\n")
            if curr_form:
                tmp.write("        </FormData>\n")
            if curr_event:
                tmp.write("      </StudyEventData>\n")

            tmp.write("    </SubjectData>\n")

        tmp.write("  </ClinicalData>\n")
        tmp.write(f'  <Association StudyOID="{study_oid}" MetaDataVersionOID="v1.0">\n')
        tmp.write('    <KeySet OID="ASSOC_1"/>\n')
        tmp.write("  </Association>\n")

        tmp.write("</ODM>\n")
        tmp_name = tmp.name

    tmp_zip_fd, tmp_zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_zip_fd)
    with zipfile.ZipFile(tmp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(tmp_name, arcname="cdisc_export.xml")

    os.remove(tmp_name)
    return tmp_zip_path
