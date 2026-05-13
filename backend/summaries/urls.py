from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    HistoryDetailView,
    HistoryListView,
    LoginPageView,
    RegisterPageView,
    create_summary,
    delete_summary,
    home,
)


urlpatterns = [
    path("", home, name="home"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("history/", HistoryListView.as_view(), name="history"),
    path("history/<int:pk>/", HistoryDetailView.as_view(), name="history_detail"),
    path("history/<int:pk>/delete/", delete_summary, name="history_delete"),
    path("api/summaries/create/", create_summary, name="create_summary"),
]
