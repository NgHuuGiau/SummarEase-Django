"""API v1 URL routes."""

from django.urls import path

from .views import create_summary_api, summary_task_status_api

app_name = "v1"

urlpatterns = [
    path("summaries/create/", create_summary_api, name="create_summary"),
    path("summaries/status/<str:task_id>/", summary_task_status_api, name="check_task_status"),
]
