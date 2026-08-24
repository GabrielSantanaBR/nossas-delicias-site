from django.urls import re_path
from .consumers import OrderChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/pedidos/(?P<order_id>\d+)/chat/$", OrderChatConsumer.as_asgi()),
]
