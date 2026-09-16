import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class RateLimitMiddleware(MiddlewareMixin):
    """Simple IP-based rate limiter using cache."""

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def __call__(self, request):
        if self._should_limit(request):
            limit_response = self._check_limit(request)
            if limit_response:
                return limit_response
        return self.get_response(request)

    def _should_limit(self, request):
        path = request.path
        return path.startswith("/api/") or path == "/create-summary/"

    def _check_limit(self, request):
        from django.conf import settings

        ip = self._get_client_ip(request)
        path = request.path
        key = f"ratelimit:{ip}:{path}"
        limit_seconds = getattr(settings, "RATE_LIMIT_SECONDS", 5)

        if limit_seconds <= 0:
            return None
        if not cache.add(key, 1, timeout=limit_seconds):
            retry_after = limit_seconds
            return JsonResponse(
                {
                    "ok": False,
                    "message": f"Quá nhiều yêu cầu. Vui lòng thử lại sau {retry_after} giây.",
                    "retry_after": retry_after,
                },
                status=429,
                headers={"Retry-After": str(retry_after)},
            )

        return None

    def _get_client_ip(self, request):
        remote_addr = request.META.get("REMOTE_ADDR", "unknown")
        if not self._is_trusted_proxy(remote_addr):
            return remote_addr

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        for candidate in reversed(forwarded_for.split(",")):
            candidate = candidate.strip()
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if not self._is_trusted_proxy(str(address)):
                return str(address)
        return remote_addr

    @staticmethod
    def _is_trusted_proxy(address):
        try:
            parsed_address = ipaddress.ip_address(address)
            return any(
                parsed_address in ipaddress.ip_network(network, strict=False)
                for network in settings.TRUSTED_PROXY_IPS
            )
        except ValueError:
            return False
