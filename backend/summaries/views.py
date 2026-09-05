import time
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm, SettingsForm, SummaryRequestForm
from .models import (
    Document,
    Summary,
    SummarySentence,
    Tag,
    _cleanup_uploaded_file,
)
from .nlp import gemini_summarize, textrank_summarize
from .nlp_utils import detect_language
from .readers import extract_text
from .signing import decrypt_value, encrypt_value

PAGE_SIZE = 12
MAX_FILE_SIZE = 10 * 1024 * 1024


def _serialize_form_errors(form) -> dict[str, list[str]]:
    return {
        field: [item["message"] for item in errors]
        for field, errors in form.errors.get_json_data(escape_html=False).items()
    }


def health(request: HttpRequest) -> HttpResponse:
    """Health check: xác nhận DB + media writable còn hoạt động."""
    from django.db import connection

    checks = {"status": "ok"}
    try:
        from django.db import transaction

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["status"] = "degraded"
        checks["database"] = f"error: {exc}"

    media = Path(settings.MEDIA_ROOT)
    try:
        media.mkdir(parents=True, exist_ok=True)
        probe = media / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["media"] = "ok"
    except OSError as exc:
        checks["status"] = "degraded"
        checks["media"] = f"error: {exc}"

    status = 200 if checks["status"] == "ok" else 503
    return JsonResponse(checks, status=status)


def home(request: HttpRequest) -> HttpResponse:
    recent_public = list(
        Summary.objects.select_related("document", "user")
        .only("title", "method", "language", "created_at", "document__title", "user__username")
        .all()[:9]
    )
    user_history: list[Summary] = []
    initial_ratio = 0.2
    if request.user.is_authenticated:
        if hasattr(request.user, "setting"):
            initial_ratio = request.user.setting.default_summary_ratio
        user_history = list(
            Summary.objects.filter(user=request.user)
            .select_related("document")
            .only("title", "method", "language", "created_at", "summary_text", "document__title")[
                :6
            ]
        )
    form = SummaryRequestForm(
        initial={"source_type": "text", "method": "textrank", "ratio": initial_ratio}
    )
    return render(
        request,
        "summaries/home.html",
        {
            "form": form,
            "recent_public": recent_public,
            "user_history": user_history,
            "gemini_available": home_gemini_available(request.user),
        },
    )


def home_gemini_available(user) -> bool:
    if settings.GEMINI_API_KEY:
        return True
    return bool(getattr(user, "setting", None) and user.setting.gemini_api_key)


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
            login(request, user)
            return redirect("home")
        return render(request, self.template_name, {"form": form})


class LoginPageView(LoginView):
    template_name = "summaries/login.html"
    authentication_form = LoginForm
    # ponytail: giới hạn đơn giản theo username, đổi sang theo IP+redis nếu cần scale
    max_failed_attempts = 5
    lockout_seconds = 15 * 60

    def _lock_key(self, username: str) -> str:
        return f"login-fail:{username.lower()}"

    def _is_locked(self, username: str) -> bool:
        return cache.get(self._lock_key(username), 0) >= self.max_failed_attempts

    def post(self, request, *args, **kwargs):
        username = self.request.POST.get("username", "")
        if username and self._is_locked(username):
            form = self.get_form()
            form.add_error(
                None,
                ValidationError(
                    "Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau 15 phút.",
                    code="locked",
                ),
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        username = form.cleaned_data.get("username", "")
        if username and not self._is_locked(username):
            key = self._lock_key(username)
            attempts = cache.get(key, 0) + 1
            cache.set(key, attempts, timeout=self.lockout_seconds)
        return super().form_invalid(form)

    def form_valid(self, form):
        username = form.cleaned_data.get("username", "")
        if username:
            cache.delete(self._lock_key(username))
        return super().form_valid(form)


class HistoryListView(LoginRequiredMixin, View):
    template_name = "summaries/history_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        base = Summary.objects.select_related("document", "user").only(
            "title",
            "method",
            "language",
            "created_at",
            "summary_text",
            "document__title",
            "document__source_type",
            "user__username",
        )
        if not request.user.is_staff:
            base = base.filter(user=request.user)
        paginator = Paginator(base, PAGE_SIZE)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        return render(
            request,
            self.template_name,
            {"page_obj": page_obj, "is_admin_view": request.user.is_staff},
        )


class HistoryDetailView(LoginRequiredMixin, View):
    template_name = "summaries/history_detail.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        queryset = Summary.objects.select_related("document", "user").prefetch_related(
            "tags", "sentences"
        )
        if not request.user.is_staff:
            queryset = queryset.filter(user=request.user)
        item = get_object_or_404(queryset, pk=pk)
        return render(
            request, self.template_name, {"item": item, "is_admin_view": request.user.is_staff}
        )


@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    setting, _ = request.user.setting.__class__.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SettingsForm(request.POST)
        if form.is_valid():
            setting.default_summary_ratio = form.cleaned_data["default_summary_ratio"]
            api_key = form.cleaned_data.get("gemini_api_key", "").strip()
            setting.gemini_api_key = encrypt_value(api_key) if api_key else ""
            setting.save(update_fields=["default_summary_ratio", "gemini_api_key"])
            messages.success(request, "Đã lưu cài đặt.")
            return redirect("settings")
    else:
        form = SettingsForm(
            initial={
                "default_summary_ratio": setting.default_summary_ratio,
                "gemini_api_key": decrypt_value(setting.gemini_api_key)
                if setting.gemini_api_key
                else "",
            }
        )

    system_has_key = bool(settings.GEMINI_API_KEY)
    return render(
        request,
        "summaries/settings.html",
        {
            "form": form,
            "setting": setting,
            "system_has_key": system_has_key,
        },
    )


@login_required
@require_POST
def delete_summary(request: HttpRequest, pk: int) -> HttpResponse:
    if request.user.is_staff:
        summary = get_object_or_404(Summary, pk=pk)
    else:
        summary = get_object_or_404(Summary, pk=pk, user=request.user)
    summary.delete()
    messages.success(request, "Đã xóa bản tóm tắt.")
    return redirect("history")


@login_required
@require_POST
def create_summary(request: HttpRequest) -> JsonResponse:
    limit = getattr(settings, "RATE_LIMIT_SECONDS", 5)
    cache_key = f"rate_limit:{request.user.id}"
    last_call = cache.get(cache_key, 0.0)
    now = time.time()
    if now - last_call < limit:
        wait = int(limit - (now - last_call))
        return JsonResponse(
            {"ok": False, "message": f"Vui lòng đợi {wait} giây trước khi gửi yêu cầu tiếp theo."},
            status=429,
        )
    cache.set(cache_key, now, limit)

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

    if uploaded_file and uploaded_file.size > MAX_FILE_SIZE:
        return JsonResponse(
            {"ok": False, "message": "Dung lượng tệp vượt quá 10MB. Vui lòng chọn tệp nhỏ hơn."},
            status=400,
        )

    try:
        if source_type == "text":
            original_text = form.cleaned_data["text"].strip()
            source_name = "Văn bản nhập tay"
        elif source_type == "url":
            source_name = form.cleaned_data["source_url"]
            original_text = extract_text(source_name)
        elif source_type == "file" and uploaded_file:
            source_name = uploaded_file.name
            temp_dir = Path(settings.MEDIA_ROOT) / "uploads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid4().hex}_{uploaded_file.name}"
            with temp_path.open("wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            original_text = extract_text(temp_path)
            stored_file_name = str(temp_path.relative_to(settings.MEDIA_ROOT))
        else:
            return JsonResponse(
                {"ok": False, "message": "Không có nội dung để tóm tắt."},
                status=400,
            )

        if not original_text.strip():
            raise ValueError("Không thể trích xuất nội dung từ nguồn đã chọn.")

        language = detect_language(original_text)
        if method == "gemini":
            user_key = decrypt_value(request.user.setting.gemini_api_key)
            result = gemini_summarize(
                original_text, ratio=ratio, language=language, user_api_key=user_key
            )
        else:
            result = textrank_summarize(original_text, ratio=ratio, language=language)

        title = result["title"][:255]

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
            tag_names = list(dict.fromkeys(kw[:100] for kw in result["keywords"]))
            if tag_names:
                all_tags = []
                for name in tag_names:
                    tag, _ = Tag.objects.get_or_create(name=name)
                    all_tags.append(tag)
                summary.tags.add(*all_tags)
            SummarySentence.objects.bulk_create(
                [
                    SummarySentence(summary=summary, sentence_text=sentence, sentence_index=index)
                    for index, sentence in enumerate(result["sentences"], start=1)
                ]
            )

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
        if stored_file_name:
            _cleanup_uploaded_file(stored_file_name)
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
