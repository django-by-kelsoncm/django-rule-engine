from django.urls import include, path

urlpatterns = [path("api/", include("django_rule_engine.api.urls"))]
