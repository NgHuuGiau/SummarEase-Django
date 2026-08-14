import secrets

from django.http import HttpRequest, HttpResponse


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com data:; "
            f"img-src 'self' data:; "
            f"connect-src 'self' https://generativelanguage.googleapis.com; "
            f"base-uri 'self'; "
            f"form-action 'self'"
        )
        return response
