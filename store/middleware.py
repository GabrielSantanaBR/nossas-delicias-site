import os

from django.conf import settings
from django.utils.cache import patch_vary_headers


class SecurityHeadersMiddleware:
    """Add conservative browser security policies without blocking app features."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Disposable demo environments may opt into an explicit staff OTP bypass.
        # Production remains protected because this requires DEBUG=1 as well as
        # DEMO_ALLOW_ADMIN_WITHOUT_OTP=1.
        if settings.DEBUG and os.environ.get('DEMO_ALLOW_ADMIN_WITHOUT_OTP') == '1':
            user = getattr(request, 'user', None)
            if user is not None and getattr(user, 'is_authenticated', False) and getattr(user, 'is_staff', False):
                user.otp_device = 'demo-bypass'

        response = self.get_response(request)
        if not response.has_header('Content-Security-Policy'):
            script_sources = ["'self'"]
            connect_sources = ["'self'", 'ws:', 'wss:', 'https://api.mercadopago.com']
            if settings.GOOGLE_ANALYTICS_MEASUREMENT_ID:
                # The tag is only injected by first-party JavaScript after a
                # visitor explicitly opts in through the cookie controls.
                script_sources.append('https://www.googletagmanager.com')
                connect_sources.extend(['https://www.google-analytics.com', 'https://region1.google-analytics.com'])
            response['Content-Security-Policy'] = '; '.join([
                "default-src 'self'",
                "base-uri 'self'",
                "object-src 'none'",
                "frame-ancestors 'none'",
                "form-action 'self' https://www.mercadopago.com https://www.mercadopago.com.br",
                "img-src 'self' data: blob: https:",
                "font-src 'self' https://fonts.gstatic.com data:",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                'script-src ' + ' '.join(script_sources),
                'connect-src ' + ' '.join(connect_sources),
                "upgrade-insecure-requests" if not settings.DEBUG else "block-all-mixed-content",
            ])
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        response.headers.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        if settings.GOOGLE_ANALYTICS_MEASUREMENT_ID:
            patch_vary_headers(response, ('Cookie',))
        if getattr(request, 'user', None) and request.user.is_authenticated:
            response.headers.setdefault('Cache-Control', 'private, no-store, max-age=0')
            response.headers.setdefault('Pragma', 'no-cache')
        return response
