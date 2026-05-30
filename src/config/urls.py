"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path

import ninja.schema
import ninja.orm
import ninja.operation
from pydantic.alias_generators import to_camel
ninja.schema.Schema.model_config["alias_generator"] = to_camel
ninja.schema.Schema.model_config["populate_by_name"] = True
ninja.orm.ModelSchema.model_config["alias_generator"] = to_camel
ninja.orm.ModelSchema.model_config["populate_by_name"] = True

original_operation_init = ninja.operation.Operation.__init__
def custom_operation_init(self, *args, **kwargs):
    if kwargs.get("by_alias") is None:
        kwargs["by_alias"] = True
    original_operation_init(self, *args, **kwargs)
ninja.operation.Operation.__init__ = custom_operation_init

from ninja import NinjaAPI

from audit.api import router as audit_router
from clinical.api import router as clinical_router
from users.api import router as users_router

api = NinjaAPI()
api.add_router("/clinical/", clinical_router)
api.add_router("/users/", users_router)
api.add_router("/audit/", audit_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
