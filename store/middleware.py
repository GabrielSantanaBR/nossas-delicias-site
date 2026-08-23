from django.conf import settings


class SecurityHeadersMiddleware:
    """Add conservative browser security policies without blocking app features."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header('Content-Security-Policy'):
            response['Content-Security-Policy'] = '; '.join([
                "default-src 'self'",
                "base-uri 'self'",
                "object-src 'none'",
                "frame-ancestors 'none'",
                "form-action 'self' https://www.mercadopago.com https://www.mercadopago.com.br",
                "img-src 'self' data: blob: https:",
                "font-src 'self' https://fonts.gstatic.com data:",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "script-src 'self' 'unsafe-inline'",
                "connect-src 'self' ws: wss: https://api.mercadopago.com",
                "upgrade-insecure-requests" if not settings.DEBUG else "block-all-mixed-content",
            ])
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(self)')
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        return response
