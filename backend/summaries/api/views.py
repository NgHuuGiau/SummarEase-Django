"""Documented DRF adapters for the existing Django summary views."""

import json

from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from summaries.views import check_task_status, create_summary


def _as_response(django_response):
    try:
        data = json.loads(django_response.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {"detail": "Không thể xử lý yêu cầu."}
    return Response(data, status=django_response.status_code)


@extend_schema(
    request=inline_serializer(
        name="SummaryCreateRequest",
        fields={
            "source_type": serializers.ChoiceField(choices=("text", "url", "file")),
            "method": serializers.ChoiceField(choices=("textrank", "gemini")),
            "text": serializers.CharField(required=False),
            "source_url": serializers.URLField(required=False),
            "upload": serializers.FileField(required=False),
            "ratio": serializers.FloatField(required=False),
        },
    ),
    responses={
        200: inline_serializer(
            name="SummaryCreateResponse",
            fields={
                "ok": serializers.BooleanField(),
                "task_id": serializers.CharField(required=False),
                "data": serializers.JSONField(required=False),
                "message": serializers.CharField(required=False),
            },
        ),
        400: inline_serializer(
            name="SummaryCreateError",
            fields={
                "ok": serializers.BooleanField(),
                "message": serializers.CharField(required=False),
                "errors": serializers.JSONField(required=False),
            },
        ),
    },
    description="Tạo bản tóm tắt. Yêu cầu phiên đăng nhập và CSRF.",
    examples=[
        OpenApiExample(
            "Tóm tắt văn bản (TextRank)",
            summary="Tóm tắt đoạn văn bản bằng TextRank",
            value={
                "source_type": "text",
                "method": "textrank",
                "text": "Django là một khung làm việc web cấp cao viết bằng Python...",
                "ratio": 0.3,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Tóm tắt URL",
            summary="Tóm tắt nội dung từ URL",
            value={
                "source_type": "url",
                "method": "textrank",
                "source_url": "https://vnexpress.net/...",
                "ratio": 0.2,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Tóm tắt thành công (sync)",
            summary="Kết quả khi TextRank chạy đồng bộ (DEBUG=True)",
            value={
                "ok": True,
                "data": {
                    "summary_id": 42,
                    "title": "Django - Framework Web Python",
                    "method": "textrank",
                    "language": "vietnamese",
                    "ratio": 0.3,
                    "summary": "Django là framework web Python...",
                    "keywords": ["django", "python", "web", "framework"],
                    "sentences": [
                        "Django là framework web Python.",
                        "Cung cấp admin, ORM, authentication...",
                    ],
                    "created_at": "2026-01-15T10:30:00Z",
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            "Tóm tắt thành công (async)",
            summary="Kết quả khi dùng Celery (production)",
            value={
                "ok": True,
                "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
            response_only=True,
        ),
        OpenApiExample(
            "Lỗi validation",
            summary="Thiếu trường bắt buộc",
            value={
                "ok": False,
                "message": "Dữ liệu không hợp lệ.",
                "errors": {"text": ["Nhập văn bản cần tóm tắt."]},
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
@api_view(["POST"])
@parser_classes([FormParser, MultiPartParser])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_summary_api(request):
    return _as_response(create_summary(request._request))


@extend_schema(
    responses={
        200: inline_serializer(
            name="SummaryTaskStatus",
            fields={
                "status": serializers.ChoiceField(choices=("pending", "done")),
                "data": serializers.JSONField(required=False),
            },
        ),
        404: inline_serializer(
            name="SummaryTaskNotFound",
            fields={"ok": serializers.BooleanField(), "message": serializers.CharField()},
        ),
    },
    description="Kiểm tra trạng thái tác vụ do chính người dùng tạo.",
    examples=[
        OpenApiExample(
            "Tác vụ đang chạy",
            summary="Tóm tắt đang được xử lý",
            value={"status": "pending"},
            response_only=True,
        ),
        OpenApiExample(
            "Tác vụ hoàn tất",
            summary="Tóm tắt đã xong, trả về kết quả",
            value={
                "status": "done",
                "data": {
                    "ok": True,
                    "data": {
                        "summary_id": 42,
                        "title": "Django - Framework Web Python",
                        "summary": "Django là framework web Python...",
                    },
                },
            },
            response_only=True,
        ),
        OpenApiExample(
            "Tác vụ không tồn tại",
            summary="Task ID không hợp lệ hoặc không thuộc user",
            value={"ok": False, "message": "Không tìm thấy tác vụ."},
            response_only=True,
            status_codes=["404"],
        ),
    ],
)
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def summary_task_status_api(request, task_id):
    return _as_response(check_task_status(request._request, task_id))
