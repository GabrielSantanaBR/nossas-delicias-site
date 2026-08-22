from django.urls import path
from . import views
from . import views_finance

urlpatterns=[
    path('',views.home,name='home'),
    path('cardapio/',views.catalog,name='catalog'),
    path('cadastro/',views.register,name='register'),
    path('minha-conta/',views.account,name='account'),
    path('carrinho/',views.cart_view,name='cart'),
    path('carrinho/adicionar/',views.add_to_cart,name='add_to_cart'),
    path('carrinho/item/<int:item_id>/atualizar/',views.update_cart_item,name='update_cart_item'),
    path('carrinho/item/<int:item_id>/remover/',views.remove_cart_item,name='remove_cart_item'),
    path('carrinho/finalizar/',views.checkout_cart,name='checkout_cart'),
    path('entrega/disponibilidade/',views.delivery_availability,name='delivery_availability'),
    path('cafeterias/',views.cafe_portal,name='cafe_portal'),
    path('cafeterias/cadastro/',views.cafe_apply,name='cafe_apply'),
    path('cafeterias/pedidos/<uuid:public_id>/editar/',views_finance.cafe_order_edit,name='cafe_order_edit'),
    path('cafeterias/pedidos/<uuid:public_id>/nota/',views_finance.cafe_note,name='cafe_note'),
    path('eventos/',views.event_portal,name='event_portal'),
    path('eventos/orcamento/',views.event_quote_create,name='event_quote_create'),
    path('pedidos/<uuid:public_id>/',views.order_detail,name='order_detail'),
    path('pedidos/<uuid:public_id>/pagar/',views.start_payment,name='start_payment'),
    path('financeiro/',views_finance.finance_dashboard,name='finance_dashboard'),
    path('financeiro/exportar.csv',views_finance.finance_export_csv,name='finance_export_csv'),
    path('pagamentos/retorno/',views.payment_return,name='payment_return'),
    path('pagamentos/mercado-pago/webhook/',views.mercado_pago_webhook,name='mp_webhook'),
]
