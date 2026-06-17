from django.views.generic import TemplateView

class DashboardView(TemplateView):
    template_name = "hub/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import CommerceAgent
        agents = CommerceAgent.objects.all()
        context["total_agents"] = agents.count()
        context["active_agents"] = agents.filter(status="ACTIVE").count()
        context["agents"] = agents
        return context
