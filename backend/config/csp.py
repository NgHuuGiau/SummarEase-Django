import secrets

from django.http import HttpRequest, HttpResponse


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        response = self.get_response(request)
        docs_page = request.path in {"/api/docs/", "/api/redoc/"}
        style_sources = f"'self' 'nonce-{nonce}' https://fonts.googleapis.com"
        image_sources = "'self' data:"
        if docs_page:
            style_sources += " https://cdn.jsdelivr.net"
            image_sources += " https://cdn.jsdelivr.net"
        response["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src {style_sources}; "
            f"font-src 'self' https://fonts.gstatic.com data:; "
            f"img-src {image_sources}; "
            f"connect-src 'self' https://generativelanguage.googleapis.com; "
            f"base-uri 'self'; "
            f"object-src 'none'; "
            f"frame-ancestors 'self'; "
            f"form-action 'self'"
        )
        return response
