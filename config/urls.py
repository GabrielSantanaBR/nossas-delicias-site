from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from store.admin_site import secure_admin_site
from store.auth_views import RateLimitedLoginView, RateLimitedPasswordResetView

urlpatterns=[
    path('nd-admin/',secure_admin_site.urls),
    path('login/',RateLimitedLoginView.as_view(template_name='registration/login.html'),name='login'),
    path('logout/',auth_views.LogoutView.as_view(),name='logout'),
    path('senha/esqueci/',RateLimitedPasswordResetView.as_view(template_name='registration/password_reset_form.html',email_template_name='registration/password_reset_email.txt',success_url=reverse_lazy('password_reset_done')),name='password_reset'),
    path('senha/enviada/',auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),name='password_reset_done'),
    path('senha/redefinir/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html',success_url=reverse_lazy('password_reset_complete')),name='password_reset_confirm'),
    path('senha/concluida/',auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),name='password_reset_complete'),
    path('',include('store.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
