"""Prometheus metrics for SummarEase."""

from django.http import HttpResponse
from django.urls import path
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

request_count = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

request_latency = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

active_requests = Gauge(
    "http_active_requests",
    "Number of active HTTP requests",
    ["method", "endpoint"],
)

summary_created = Counter(
    "summaries_created_total",
    "Total summaries created",
    ["method", "source_type"],
)

summary_failed = Counter(
    "summaries_failed_total",
    "Total summary creation failures",
    ["method", "error_type"],
)

gemini_api_calls = Counter(
    "gemini_api_calls_total",
    "Total Gemini API calls",
    ["status"],
)

cache_hits = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

cache_misses = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)


def metrics_view(request):
    """Prometheus /metrics endpoint."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


class PrometheusMiddleware:
    """Middleware to collect request metrics."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        active_requests.labels(method=request.method, endpoint=request.path).inc()
        response = self.get_response(request)
        active_requests.labels(method=request.method, endpoint=request.path).dec()

        request_count.labels(
            method=request.method,
            endpoint=request.path,
            status=response.status_code,
        ).inc()

        return response


urlpatterns = [
    path("", metrics_view, name="prometheus_metrics"),
]
