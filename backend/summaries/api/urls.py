"""API v1 URL routes."""

from django.urls import path
from summaries.views import check_task_status, create_summary

app_name = "v1"

urlpatterns = [
    path("summaries/create/", create_summary, name="create_summary"),
    path("summaries/status/<str:task_id>/", check_task_status, name="check_task_status"),
]
