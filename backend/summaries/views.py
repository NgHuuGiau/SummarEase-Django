from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm, SummaryRequestForm
from .models import Document, Summary, SummarySentence, Tag, UserProfile, UserSetting
from .nlp import detect_language, extract_text, gemini_summarize, textrank_summarize


def _ensure_user_defaults(user) -> None:
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": UserProfile.ROLE_USER})
    UserSetting.objects.get_or_create(user=user, defaults={"default_summary_ratio": 0.2, "language_preference": "auto"})
    if user.is_superuser and profile.role != UserProfile.ROLE_ADMIN:
        profile.role = UserProfile.ROLE_ADMIN
        profile.save(update_fields=["role"])


def _serialize_form_errors(form) -> dict[str, list[str]]:
    return {
        field: [str(message) for message in errors]
        for field, errors in form.errors.get_json_data(escape_html=False).items()
        for errors in [[item["message"] for item in errors]]
    }


def home(request: HttpRequest) -> HttpResponse:
    recent_public = Summary.objects.select_related("document", "user").all()[:9]
    user_history = []
    initial_ratio = 0.2
    if request.user.is_authenticated:
        _ensure_user_defaults(request.user)
        user_history = Summary.objects.filter(user=request.user).select_related("document")[:6]
        initial_ratio = request.user.setting.default_summary_ratio
    form = SummaryRequestForm(initial={"source_type": "text", "method": "textrank", "ratio": initial_ratio})
    return render(
        request,
        "summaries/home.html",
        {
            "form": form,
            "recent_public": recent_public,
            "user_history": user_history,
        },
    )


class RegisterPageView(View):
    template_name = "summaries/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {"form": RegisterForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.email = form.cleaned_data["email"]
            user.save(update_fields=["email"])
            _ensure_user_defaults(user)
            login(request, user)
            return redirect("home")
        return render(request, self.template_name, {"form": form})


class LoginPageView(LoginView):
    template_name = "summaries/login.html"
    authentication_form = LoginForm


class HistoryListView(LoginRequiredMixin, View):
    template_name = "summaries/history_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_staff:
            items = Summary.objects.select_related("document", "user")
        else:
            items = Summary.objects.filter(user=request.user).select_related("document", "user")
        return render(request, self.template_name, {"items": items, "is_admin_view": request.user.is_staff})


class HistoryDetailView(LoginRequiredMixin, View):
    template_name = "summaries/history_detail.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        queryset = Summary.objects.select_related("document", "user")
        if not request.user.is_staff:
            queryset = queryset.filter(user=request.user)
        item = get_object_or_404(queryset, pk=pk)
        return render(request, self.template_name, {"item": item, "is_admin_view": request.user.is_staff})


@login_required
@require_POST
def delete_summary(request: HttpRequest, pk: int) -> HttpResponse:
    summary = get_object_or_404(Summary, pk=pk, user=request.user)
    summary.delete()
    messages.success(request, "Đã xóa bản tóm tắt.")
    return redirect("history")


@login_required
@require_POST
def create_summary(request: HttpRequest) -> JsonResponse:
    _ensure_user_defaults(request.user)
    form = SummaryRequestForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _serialize_form_errors(form)}, status=400)

    source_type = form.cleaned_data["source_type"]
    method = form.cleaned_data["method"]
    ratio = form.cleaned_data["ratio"]

    source_name = ""
    original_text = ""
    stored_file_name = ""
    uploaded_file = form.cleaned_data.get("upload")

    try:
        if source_type == "text":
            original_text = form.cleaned_data["text"].strip()
            source_name = "Văn bản nhập tay"
        elif source_type == "url":
            source_name = form.cleaned_data["source_url"]
            original_text = extract_text(source_name)
        else:
            source_name = uploaded_file.name
            temp_dir = Path(settings.MEDIA_ROOT) / "uploads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid4().hex}_{uploaded_file.name}"
            with temp_path.open("wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            original_text = extract_text(temp_path)
            stored_file_name = str(temp_path.relative_to(settings.MEDIA_ROOT))

        language = detect_language(original_text)
        if method == "gemini":
            result = gemini_summarize(original_text, ratio=ratio, language=language)
        else:
            result = textrank_summarize(original_text, ratio=ratio, language=language)

        title = (result["title"] or "Tóm tắt tài liệu")[:255]

        with transaction.atomic():
            document = Document.objects.create(
                user=request.user,
                source_type=source_type,
                title=title,
                source_name=source_name[:255],
                uploaded_file=stored_file_name,
                content=original_text,
            )
            summary = Summary.objects.create(
                document=document,
                user=request.user,
                title=title,
                method=method,
                language=result["language"],
                ratio=ratio,
                summary_text=result["summary"],
            )
            tag_objects = []
            for keyword in result["keywords"]:
                tag, _ = Tag.objects.get_or_create(name=keyword[:100])
                tag_objects.append(tag)
            if tag_objects:
                summary.tags.set(tag_objects)
            SummarySentence.objects.bulk_create(
                [
                    SummarySentence(summary=summary, sentence_text=sentence, sentence_index=index)
                    for index, sentence in enumerate(result["sentences"], start=1)
                ]
            )
            request.user.setting.default_summary_ratio = ratio
            request.user.setting.save(update_fields=["default_summary_ratio"])

        return JsonResponse(
            {
                "ok": True,
                "data": {
                    "id": summary.id,
                    "title": summary.title,
                    "language": summary.language,
                    "method": summary.method,
                    "ratio": summary.ratio,
                    "summary": result["summary"],
                    "highlighted_summary": result["highlighted_summary"],
                    "keywords": result["keywords"],
                    "source_type": source_type,
                    "source_name": source_name,
                    "created_at": summary.created_at.strftime("%d/%m/%Y %H:%M"),
                    "history_url": reverse("history_detail", kwargs={"pk": summary.id}),
                },
            }
        )
    except (OSError, ValueError, ValidationError) as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
