from django.urls import path
from . import views

urlpatterns=[
    path('',views.home,name='home'),
    path('cardapio/',views.catalog,name='catalog'),
    path('cadastro/',views.register,name='register'),
    path('minha-conta/',views.account,name='account'),
    path('entrega/disponibilidade/',views.delivery_availability,name='delivery_availability'),
    path('pedidos/criar/',views.create_order,name='create_order'),
    path('pedidos/<uuid:public_id>/',views.order_detail,name='order_detail'),
    path('pedidos/<uuid:public_id>/pagar/',views.start_payment,name='start_payment'),
    path('pagamentos/retorno/',views.payment_return,name='payment_return'),
    path('pagamentos/mercado-pago/webhook/',views.mercado_pago_webhook,name='mp_webhook'),
]
