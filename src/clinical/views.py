import ast

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django_celery_results.models import TaskResult

from .models import Provider, Record, Subject, SyncJob
from .tasks import reconstruct_subject_timeline


class DashboardView(TemplateView):
    template_name = "clinical/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider_id = self.request.GET.get("provider_id")

        providers = Provider.objects.all()
        context["providers"] = providers

        if provider_id:
            try:
                selected_provider = Provider.objects.get(id=provider_id)
            except Provider.DoesNotExist:
                selected_provider = providers.first()
        else:
            selected_provider = providers.first()

        context["selected_provider"] = selected_provider

        if selected_provider:
            # Sync jobs
            context["sync_jobs"] = SyncJob.objects.filter(provider=selected_provider).order_by("-created_at")[:10]

            # Longitudinal Data Visualization
            # metrics regarding patient timelines, baseline dates, offsets
            subjects = Subject.objects.filter(provider=selected_provider)
            total_subjects = subjects.count()
            subjects_with_baseline = [s for s in subjects if s.baseline_date]

            # Entities with offsets
            records_with_offset = Record.objects.filter(provider=selected_provider, offset_days__isnull=False).count()
            total_records = Record.objects.filter(provider=selected_provider).count()

            context["metrics"] = {
                "total_subjects": total_subjects,
                "subjects_with_baseline": len(subjects_with_baseline),
                "records_with_offset": records_with_offset,
                "total_records": total_records,
                "mapping_success_rate": self._calculate_mapping_rate(selected_provider),
            }

        # Timeline Reconstruction Tasks (Celery tasks)
        context["reconstruction_tasks"] = TaskResult.objects.filter(
            task_name="clinical.tasks.reconstruct_subject_timeline"
        ).order_by("-date_done")[:10]

        return context

    def _calculate_mapping_rate(self, provider):
        # success rates for clinical entity mapping
        from .models import SyncTask

        tasks = SyncTask.objects.filter(job__provider=provider)
        total = tasks.count()
        if total == 0:
            return 100.0
        completed = tasks.filter(status="COMPLETED").count()
        return round((completed / total) * 100, 2)


class RetriggerTimelineTaskView(View):
    def post(self, request, *args, **kwargs):
        task_id = request.POST.get("task_id")
        if task_id:
            try:
                task_result = TaskResult.objects.get(task_id=task_id)
                # Celery stores task_args as a string repr of a tuple, like "('123',)"
                args_list = ast.literal_eval(task_result.task_args)
                if args_list and len(args_list) > 0:
                    subject_id = args_list[0]
                    reconstruct_subject_timeline.delay(subject_id)
            except Exception:  # noqa: S110
                pass
        return HttpResponseRedirect(reverse("dashboard"))
