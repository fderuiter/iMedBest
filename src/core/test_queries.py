import pytest
from datetime import UTC, datetime
from clinical.models import Provider, Study
from clinical.services import StudySyncEngine
from core.models import Query, QueryComment, Subject, Variable

@pytest.mark.django_db
def test_sync_queries_create():
    provider = Provider.objects.create(name="iMednet")
    study = Study.objects.create(name="Test Study", provider=provider, external_id="study1")
    subject = Subject.objects.create(study=study, imednet_id="1001", subject_key="S001", subject_status="Active")

    query_data = [
        {
            "annotationId": "ann1",
            "subjectId": 1001,
            "subjectOid": "S_OID1",
            "annotationType": "Query",
            "type": "Manual",
            "description": "Please verify age",
            "recordId": 123,
            "variable": "Var1",
            "subjectKey": "S001",
            "comments": [
                {
                    "comment": "Initial query",
                    "user": "dr_smith",
                    "dateCreated": [2023, 10, 27, 10, 0, 0, 0]
                }
            ]
        }
    ]

    stats = StudySyncEngine.sync_queries(study, query_data)

    assert stats["created"] == 1
    assert Query.objects.count() == 1
    query = Query.objects.get(imednet_id="ann1")
    assert query.description == "Please verify age"
    assert query.subject == subject
    assert query.imednet_record_id == 123
    assert query.comments.count() == 1
    comment = query.comments.first()
    assert comment.comment == "Initial query"
    assert comment.user_raw == "dr_smith"
    assert comment.date_created == datetime(2023, 10, 27, 10, 0, 0, tzinfo=UTC)

@pytest.mark.django_db
def test_sync_queries_rebuild_comments():
    provider = Provider.objects.create(name="iMednet")
    study = Study.objects.create(name="Test Study", provider=provider, external_id="study1")
    subject = Subject.objects.create(study=study, imednet_id="1001", subject_key="S001", subject_status="Active")

    query_data = [
        {
            "annotationId": "ann1",
            "subjectId": 1001,
            "subjectOid": "S_OID1",
            "annotationType": "Query",
            "description": "Desc",
            "variable": "Var1",
            "subjectKey": "S001",
            "comments": [{"comment": "C1", "user": "U1", "dateCreated": [2023, 1, 1]}]
        }
    ]

    StudySyncEngine.sync_queries(study, query_data)
    assert QueryComment.objects.count() == 1

    # Update with new comments
    query_data[0]["comments"] = [
        {"comment": "C1", "user": "U1", "dateCreated": [2023, 1, 1]},
        {"comment": "C2", "user": "U2", "dateCreated": [2023, 1, 2]}
    ]

    stats = StudySyncEngine.sync_queries(study, query_data)
    assert stats["updated"] == 1
    query = Query.objects.get(imednet_id="ann1")
    assert query.comments.count() == 2
    assert set(query.comments.values_list("comment", flat=True)) == {"C1", "C2"}

@pytest.mark.django_db
def test_sync_queries_partial_failure():
    provider = Provider.objects.create(name="iMednet")
    study = Study.objects.create(name="Test Study", provider=provider, external_id="study1")
    Subject.objects.create(study=study, imednet_id="1001", subject_key="S001", subject_status="Active")

    query_data = [
        {
            "annotationId": "ann1",
            "subjectId": 1001,
            "subjectOid": "S_OID1",
            "annotationType": "Query",
            "description": "Valid",
            "variable": "Var1",
            "subjectKey": "S001"
        },
        {
            "annotationId": "ann2",
            "subjectId": 9999, # Missing subject
            "subjectOid": "S_OID2",
            "annotationType": "Query",
            "description": "Invalid",
            "variable": "Var1",
            "subjectKey": "S002"
        }
    ]

    stats = StudySyncEngine.sync_queries(study, query_data)
    assert stats["created"] == 1
    assert stats["failed"] == 1
    assert Query.objects.count() == 1

@pytest.mark.django_db
def test_sync_queries_variable_lookup():
    provider = Provider.objects.create(name="iMednet")
    study = Study.objects.create(name="Test Study", provider=provider, external_id="study1")
    Subject.objects.create(study=study, imednet_id="1001", subject_key="S001", subject_status="Active")
    from core.models import Form
    form = Form.objects.create(study=study, imednet_id="f1", form_key="FK1", form_name="Form 1", revision=1)
    variable = Variable.objects.create(
        study=study, form=form, imednet_id="v1", variable_name="AgeVar", variable_oid="AGE_OID", sequence=1, revision=1
    )

    query_data = [
        {
            "annotationId": "ann1",
            "subjectId": 1001,
            "subjectOid": "S_OID1",
            "annotationType": "Query",
            "description": "Verify Age",
            "variable": "AgeVar",
            "subjectKey": "S001"
        }
    ]

    StudySyncEngine.sync_queries(study, query_data)
    query = Query.objects.get(imednet_id="ann1")
    assert query.variable_ref == variable

    # Test lookup by OID
    query_data[0]["annotationId"] = "ann2"
    query_data[0]["variable"] = "AGE_OID"
    StudySyncEngine.sync_queries(study, query_data)
    query2 = Query.objects.get(imednet_id="ann2")
    assert query2.variable_ref == variable
