from ninja import ModelSchema, Router
from django.shortcuts import get_object_or_404
from .models import Job

router = Router()

class JobSchemaOut(ModelSchema):
    class Meta:
        model = Job
        fields = ["id", "status", "job_type", "payload", "result", "error_log", "created_at", "updated_at"]

@router.get("/{job_id}", response=JobSchemaOut)
def get_job(request, job_id: str):
    return get_object_or_404(Job, id=job_id)

@router.get("/", response=list[JobSchemaOut])
def list_jobs(request):
    return Job.objects.all()
