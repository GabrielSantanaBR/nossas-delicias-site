"""Small, signed cookie-preference helpers.

The preference contains no identifier or browsing history. It only records the
visitor's current analytics choice and the policy version used for that choice.
"""

from django.conf import settings
from django.core import signing


COOKIE_NAME = 'nd_cookie_preferences'
COOKIE_SALT = 'store.cookie-preferences'


def consent_state(request):
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return 'unknown'
    try:
        payload = signing.loads(raw, salt=COOKIE_SALT, max_age=settings.COOKIE_CONSENT_MAX_AGE)
    except signing.BadSignature:
        return 'unknown'
    if not isinstance(payload, dict) or payload.get('version') != settings.PRIVACY_POLICY_VERSION:
        return 'unknown'
    return 'granted' if payload.get('analytics') is True else 'denied'


def set_consent(response, analytics):
    payload = {
        'version': settings.PRIVACY_POLICY_VERSION,
        'analytics': bool(analytics),
    }
    response.set_cookie(
        COOKIE_NAME,
        signing.dumps(payload, salt=COOKIE_SALT),
        max_age=settings.COOKIE_CONSENT_MAX_AGE,
        secure=not settings.DEBUG,
        httponly=True,
        samesite='Lax',
    )
    return response
