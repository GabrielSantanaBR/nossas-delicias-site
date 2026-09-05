from django.conf import settings

from .privacy import consent_state


def privacy(request):
    """Expose only consent state and the configured GA4 public measurement ID."""
    return {
        'privacy_analytics_id': settings.GOOGLE_ANALYTICS_MEASUREMENT_ID,
        'privacy_consent_state': consent_state(request),
        'privacy_policy_version': settings.PRIVACY_POLICY_VERSION,
    }
