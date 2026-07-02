from datetime import datetime

import pytest
from pydantic import ValidationError

from core.models import Subject
from core.schemas import ResilientDateSchema, SubjectIn, SubjectOut


@pytest.mark.django_db
def test_subject_in_extra_fields():
    """Verify that extra fields are forbidden in SubjectIn."""
    with pytest.raises(ValidationError):
        SubjectIn(
            subject_status="Active",
            illegal_field="should fail"
        )

@pytest.mark.django_db
def test_subject_in_read_only_fields():
    """Verify that read-only fields like imednet_id are not allowed in SubjectIn."""
    # imednet_id is not in SubjectIn.Meta.fields, so Pydantic should reject it if extra='forbid'
    with pytest.raises(ValidationError):
        SubjectIn(
            subject_status="Active",
            imednet_id="EXT123"
        )

@pytest.mark.django_db
def test_resilient_date_parsing():
    """Test iMednet date array parsing."""
    class DateModel(ResilientDateSchema):
        my_date: datetime

    # Valid array [year, month, day, hour, minute, second, nanoseconds]
    data = {"my_date": [2023, 10, 27, 14, 30, 0, 0]}
    obj = DateModel(**data)
    assert obj.my_date == datetime(2023, 10, 27, 14, 30, 0)

    # Standard ISO string should also work if Pydantic supports it
    data2 = {"my_date": "2023-10-27T14:30:00"}
    obj2 = DateModel(**data2)
    assert obj2.my_date == datetime(2023, 10, 27, 14, 30, 0)

@pytest.mark.django_db
def test_subject_out_serialization(db):
    """Test SubjectOut serialization with nested data (if any)."""
    from clinical.models import Provider, Site, Study
    provider = Provider.objects.create(name="Test Provider")
    study = Study.objects.create(name="Test Study", provider=provider, external_id="S1")
    site = Site.objects.create(name="Test Site", study=study, provider=provider, external_id="SITE1")

    subj = Subject.objects.create(
        study=study,
        site_name_raw="Test Site",
        imednet_id="SUBJ1",
        subject_oid="OID1",
        subject_key="K1",
        subject_status="Enrolled"
    )

    out = SubjectOut.from_orm(subj)
    assert out.imednet_id == "SUBJ1"
    assert out.subject_key == "K1"
    # CamelCase check
    data = out.model_dump(by_alias=True)
    assert "imednetId" in data
    assert "subjectKey" in data
