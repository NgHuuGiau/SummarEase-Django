"""Documented DRF adapters for the existing Django summary views."""

import json

from drf_spectacular.utils import extend_schema, inline_serializer
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
)
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def summary_task_status_api(request, task_id):
    return _as_response(check_task_status(request._request, task_id))
