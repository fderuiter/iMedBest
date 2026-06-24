from django.views.generic import TemplateView


class LoginView(TemplateView):
    template_name = "users/login.html"


from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"status": "healthy", "user": request.user.username})
