from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("minha-conta/", views.account, name="account"),
    path("pedidos/<int:pk>/", views.order_detail, name="order_detail"),
    path("entregas/disponibilidade/", views.delivery_availability, name="delivery_availability"),
]
