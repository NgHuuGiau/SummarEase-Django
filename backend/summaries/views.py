from pathlib import Path

from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST

from .batch import create_batch_from_urls, create_batch_from_zip
from .exports import export_summary
from .forms import LoginForm, RegisterForm, SettingsForm, SummaryRequestForm
from .models import Summary
from .sharing import generate_share_token, get_share_url, get_shared_summary
from .webhooks import WebhookRegistration

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

        # Search query
        search_query = request.GET.get("q", "").strip()
        if search_query:
            base = Summary.search(request.user, search_query)

        paginator = Paginator(base, PAGE_SIZE)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        return render(
            request,
            self.template_name,
            {"page_obj": page_obj, "is_admin_view": request.user.is_staff, "search_query": search_query},
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
            from .signing import encrypt_value
            setting.gemini_api_key = encrypt_value(api_key) if api_key else ""
            setting.save(update_fields=["default_summary_ratio", "gemini_api_key"])
            messages.success(request, "Đã lưu cài đặt.")
            return redirect("settings")
    else:
        form = SettingsForm(
            initial={
                "default_summary_ratio": setting.default_summary_ratio,
                "gemini_api_key": "",
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
    form = SummaryRequestForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _serialize_form_errors(form)}, status=400)

    from .services import SummaryService
    service = SummaryService(request.user)

    source_type = form.cleaned_data["source_type"]
    method = form.cleaned_data["method"]
    ratio = form.cleaned_data["ratio"]

    kwargs = {}
    if source_type == "text":
        kwargs["text"] = form.cleaned_data["text"].strip()
    elif source_type == "url":
        kwargs["source_url"] = form.cleaned_data["source_url"]
    elif source_type == "file":
        kwargs["uploaded_file"] = form.cleaned_data.get("upload")

    result = service.create_summary(source_type, method, ratio, **kwargs)
    status = result.pop("status", 200)
    return JsonResponse(result, status=status)


@login_required
def check_task_status(request: HttpRequest, task_id: str) -> JsonResponse:
    result = AsyncResult(task_id)
    if result.ready():
        return JsonResponse({"status": "done", "data": result.result})
    return JsonResponse({"status": "pending"})


@login_required
def export_summary_view(request: HttpRequest, pk: int, format: str) -> HttpResponse:
    """Export summary as PDF, DOCX, or Markdown."""
    return export_summary(request, pk, format)


@login_required
@require_POST
def batch_summarize_zip(request: HttpRequest) -> JsonResponse:
    """Process multiple files from a ZIP archive."""
    form = SummaryRequestForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _serialize_form_errors(form)}, status=400)

    method = form.cleaned_data["method"]
    ratio = form.cleaned_data["ratio"]
    uploaded_file = request.FILES.get("zip_file")

    if not uploaded_file:
        return JsonResponse(
            {"ok": False, "errors": {"zip_file": ["Chọn file ZIP để tải lên."]}}, status=400
        )

    if method == "gemini":
        user_api_key = ""
        if hasattr(request.user, "setting") and request.user.setting.gemini_api_key:
            from .signing import decrypt_value
            user_api_key = decrypt_value(request.user.setting.gemini_api_key)
        if not user_api_key and not getattr(settings, "GEMINI_API_KEY", ""):
            return JsonResponse(
                {"ok": False, "message": "Thiếu GEMINI_API_KEY. Vui lòng cấu hình trong settings cá nhân hoặc file .env."},
                status=400,
            )
    else:
        user_api_key = ""

    result = create_batch_from_zip(request.user, uploaded_file, method, ratio, user_api_key)
    status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=status)


@login_required
@require_POST
def batch_summarize_urls(request: HttpRequest) -> JsonResponse:
    """Process multiple URLs at once."""
    import json

    try:
        data = json.loads(request.body)
        urls = data.get("urls", [])
        method = data.get("method", "textrank")
        ratio = float(data.get("ratio", 0.2))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return JsonResponse({"ok": False, "message": "Dữ liệu không hợp lệ: " + str(exc)}, status=400)

    if not urls:
        return JsonResponse({"ok": False, "message": "Danh sách URL trống."}, status=400)

    if method == "gemini":
        user_api_key = ""
        if hasattr(request.user, "setting") and request.user.setting.gemini_api_key:
            from .signing import decrypt_value
            user_api_key = decrypt_value(request.user.setting.gemini_api_key)
        if not user_api_key and not getattr(settings, "GEMINI_API_KEY", ""):
            return JsonResponse(
                {"ok": False, "message": "Thiếu GEMINI_API_KEY. Vui lòng cấu hình trong settings cá nhân hoặc file .env."},
                status=400,
            )
    else:
        user_api_key = ""

    result = create_batch_from_urls(request.user, urls, method, ratio, user_api_key)
    status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=status)


@login_required
@require_POST
def create_share_link(request: HttpRequest, pk: int) -> JsonResponse:
    """Create a shareable link for a summary."""
    summary = get_object_or_404(
        Summary.objects.select_related("document"),
        pk=pk,
        user=request.user,
    )
    expiry_days = int(request.POST.get("expiry_days", 7))
    token = generate_share_token(summary, expiry_days)
    share_url = get_share_url(summary, request, expiry_days)
    return JsonResponse({
        "ok": True,
        "share_url": share_url,
        "token": token,
        "expires_in_days": expiry_days,
    })


def shared_summary_view(request: HttpRequest, token: str) -> HttpResponse:
    """Public view for shared summary (no login required)."""
    summary = get_shared_summary(request, token)
    return render(
        request,
        "summaries/shared_detail.html",
        {"item": summary, "is_shared": True},
    )


@login_required
def webhook_list(request: HttpRequest) -> HttpResponse:
    """List and manage webhook registrations."""
    webhooks = WebhookRegistration.objects.filter(user=request.user).order_by("-created_at")

    if request.method == "POST":
        url = request.POST.get("url", "").strip()
        events = request.POST.getlist("events")
        if not url:
            messages.error(request, "URL không được để trống.")
        elif not events:
            messages.error(request, "Chọn ít nhất một sự kiện.")
        else:
            import secrets
            secret = secrets.token_urlsafe(32)
            WebhookRegistration.objects.create(
                user=request.user,
                url=url,
                secret=secret,
                events=events,
            )
            messages.success(request, "Đã tạo webhook mới.")
            return redirect("webhook_list")

    return render(request, "summaries/webhook_list.html", {"webhooks": webhooks})


@login_required
@require_POST
def webhook_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a webhook registration."""
    webhook = get_object_or_404(WebhookRegistration, pk=pk, user=request.user)
    webhook.delete()
    messages.success(request, "Đã xóa webhook.")
    return redirect("webhook_list")


@login_required
@require_POST
def webhook_test(request: HttpRequest, pk: int) -> JsonResponse:
    """Send a test webhook."""
    from .webhooks import _build_webhook_payload, _deliver_webhook

    webhook = get_object_or_404(WebhookRegistration, pk=pk, user=request.user)

    # Create a dummy summary for test
    test_summary = Summary(
        id=0,
        title="Test Webhook",
        method="textrank",
        language="vietnamese",
        ratio=0.3,
        summary_text="Đây là bản tóm tắt test để kiểm tra webhook.",
        created_at=timezone.now(),
    )
    test_summary.document = type('obj', (object,), {
        'source_type': 'text',
        'source_name': 'Test',
    })()
    test_summary.tags = type('obj', (object,), {
        'values_list': lambda *a, **k: iter([]),
    })()
    test_summary.user = request.user

    payload = _build_webhook_payload(test_summary, "summary.completed")
    success = _deliver_webhook(webhook, payload)

    return JsonResponse({
        "ok": success,
        "message": "Test webhook sent successfully" if success else "Failed to send test webhook",
    })
