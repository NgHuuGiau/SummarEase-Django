from django.contrib.auth.views import LogoutView
from django.http import HttpResponse, JsonResponse
from django.urls import path

from .views import (
    HistoryDetailView,
    HistoryListView,
    LoginPageView,
    RegisterPageView,
    create_summary,
    delete_summary,
    home,
    settings_view,
)

urlpatterns = [
    path("", home, name="home"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("settings/", settings_view, name="settings"),
    path("history/", HistoryListView.as_view(), name="history"),
    path("history/<int:pk>/", HistoryDetailView.as_view(), name="history_detail"),
    path("history/<int:pk>/delete/", delete_summary, name="history_delete"),
    path("api/summaries/create/", create_summary, name="create_summary"),
    path("health/", lambda r: JsonResponse({"status": "ok"}), name="health"),
    path("robots.txt", lambda r: HttpResponse("User-agent: *\nDisallow: /admin/\nDisallow: /settings/\nDisallow: /history/\nAllow: /\n", content_type="text/plain")),
]
