"""API URLs for rule validation."""

from django.urls import path
from .views import explain_rule, validate_rule

urlpatterns = [
    path('validate-rule/', validate_rule, name='validate_rule'),
    path('explain-rule/', explain_rule, name='explain_rule'),
]
