from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.http import HttpRequest, HttpResponse
from django.urls import path, reverse_lazy

from .views import (
    HistoryDetailView,
    HistoryListView,
    LoginPageView,
    RegisterPageView,
    batch_summarize_urls,
    batch_summarize_zip,
    check_task_status,
    create_share_link,
    create_summary,
    delete_summary,
    export_summary_view,
    health,
    home,
    settings_view,
    shared_summary_view,
    webhook_list,
    webhook_delete,
    webhook_test,
)

_ROBOTS_TXT = (
    "User-agent: *\nDisallow: /admin/\nDisallow: /settings/\nDisallow: /history/\nAllow: /\n"
)

_SECURITY_TXT = (
    "Contact: mailto:security@example.com\n"
    "Preferred-Languages: vi, en\n"
    "Policy: https://github.com/NgHuuGiau/SummarEase-Django/security\n"
    "Expires: 2027-01-01T00:00:00.000Z\n"
)


def _robots_txt(_request: HttpRequest) -> HttpResponse:
    return HttpResponse(_ROBOTS_TXT, content_type="text/plain")


def _security_txt(_request: HttpRequest) -> HttpResponse:
    return HttpResponse(_SECURITY_TXT, content_type="text/plain")


urlpatterns = [
    path("", home, name="home"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="summaries/password_reset.html",
            email_template_name="summaries/password_reset_email.txt",
            subject_template_name="summaries/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="summaries/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="summaries/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="summaries/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("settings/", settings_view, name="settings"),
    path("history/", HistoryListView.as_view(), name="history"),
    path("history/<int:pk>/", HistoryDetailView.as_view(), name="history_detail"),
    path("history/<int:pk>/delete/", delete_summary, name="history_delete"),
    path("history/<int:pk>/export/<str:format>/", export_summary_view, name="history_export"),
    path("history/<int:pk>/share/", create_share_link, name="history_share"),
    path("share/<str:token>/", shared_summary_view, name="shared_summary"),
    path("api/summaries/create/", create_summary, name="create_summary"),
    path("api/summaries/status/<str:task_id>/", check_task_status, name="check_task_status"),
    path("api/summaries/batch/zip/", batch_summarize_zip, name="batch_summarize_zip"),
    path("api/summaries/batch/urls/", batch_summarize_urls, name="batch_summarize_urls"),
    path("webhooks/", webhook_list, name="webhook_list"),
    path("webhooks/<int:pk>/delete/", webhook_delete, name="webhook_delete"),
    path("webhooks/<int:pk>/test/", webhook_test, name="webhook_test"),
    path("health/", health, name="health"),
    path("robots.txt", _robots_txt, name="robots_txt"),
    path(".well-known/security.txt", _security_txt, name="security_txt"),
]
