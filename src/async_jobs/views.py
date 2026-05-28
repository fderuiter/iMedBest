from django.http import JsonResponse
from django.shortcuts import render

from .models import Metric


def dashboard(request):
    return render(request, 'async_jobs/dashboard.html')

def metrics_api(request):
    # Get last 50 data points for queue_depth
    queue_depth_metrics = Metric.objects.filter(name='queue_depth').order_by('-timestamp')[:50]
    # Get last 50 data points for task_success
    task_success_metrics = Metric.objects.filter(name='task_success').order_by('-timestamp')[:50]

    data = {
        'queue_depth': [
            {'timestamp': m.timestamp.isoformat(), 'value': m.value}
            for m in reversed(queue_depth_metrics)
        ],
        'task_success': [
            {'timestamp': m.timestamp.isoformat(), 'value': m.value}
            for m in reversed(task_success_metrics)
        ]
    }
    return JsonResponse(data)
