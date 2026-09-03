from django.contrib.auth.views import LoginView, PasswordResetView
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from .forms import CustomerAuthenticationForm

@method_decorator(ratelimit(key='ip',rate='8/m',method='POST',block=True),name='dispatch')
class RateLimitedLoginView(LoginView):
    authentication_form = CustomerAuthenticationForm

@method_decorator(ratelimit(key='ip',rate='4/h',method='POST',block=True),name='dispatch')
class RateLimitedPasswordResetView(PasswordResetView):
    pass
