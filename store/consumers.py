import time
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache
from django.db import DatabaseError

from .models import Conversation, Message


def can_user_access_order_chat(user_id, order_id):
    """Keep public chat access restricted to the customer who owns the order."""
    return Conversation.objects.filter(order__public_id=order_id, customer_id=user_id).exists()


def consume_shared_chat_quota(user_id, order_id, limit=12, window_seconds=10, now=None):
    """Apply a fixed-window quota that survives WebSocket reconnects.

    The in-connection rolling limit remains the first line of defence. If the
    shared cache is momentarily unavailable, chat stays usable while that local
    limit still protects the connection.
    """
    timestamp = time.time() if now is None else now
    bucket = int(timestamp // window_seconds)
    key = f'order-chat-rate:{user_id}:{order_id}:{bucket}'
    timeout = max(window_seconds * 2, 1)
    try:
        if cache.add(key, 1, timeout=timeout):
            return True
        try:
            count = cache.incr(key)
        except ValueError:
            return cache.add(key, 1, timeout=timeout)
        return count <= limit
    except Exception:
        return True


class OrderChatConsumer(AsyncJsonWebsocketConsumer):
    MAX_MESSAGES_PER_WINDOW = 12
    WINDOW_SECONDS = 10

    async def connect(self):
        user = self.scope['user']
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.message_times = deque()

        if not user.is_authenticated or not await self.can_access(user.id, self.order_id):
            await self.close(code=4403)
            return

        self.group = f'order_chat_{self.order_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = str(content.get('message') or '').strip()
        if not text:
            return
        if len(text) > 4000:
            await self.send_json({'error': 'Mensagem muito longa.'})
            return

        now = time.monotonic()
        while self.message_times and now - self.message_times[0] > self.WINDOW_SECONDS:
            self.message_times.popleft()
        if len(self.message_times) >= self.MAX_MESSAGES_PER_WINDOW:
            await self.send_json({'error': 'Muitas mensagens em pouco tempo. Aguarde alguns segundos.'})
            return
        if not await self.shared_quota_allows(self.scope['user'].id, self.order_id):
            await self.send_json({'error': 'Muitas mensagens em pouco tempo. Aguarde alguns segundos.'})
            return

        self.message_times.append(now)
        payload = await self.save_message(self.scope['user'].id, self.order_id, text)
        if payload.get('error'):
            await self.send_json(payload)
            return
        await self.channel_layer.group_send(self.group, {'type': 'chat.message', 'payload': payload})

    async def chat_message(self, event):
        await self.send_json(event['payload'])

    @database_sync_to_async
    def can_access(self, user_id, order_id):
        # Operational staff reply through the OTP-protected management center.
        # The public socket is deliberately restricted to the order owner.
        return can_user_access_order_chat(user_id, order_id)

    @database_sync_to_async
    def shared_quota_allows(self, user_id, order_id):
        return consume_shared_chat_quota(
            user_id,
            order_id,
            limit=self.MAX_MESSAGES_PER_WINDOW,
            window_seconds=self.WINDOW_SECONDS,
        )

    @database_sync_to_async
    def save_message(self, user_id, order_id, text):
        try:
            convo = Conversation.objects.select_related('order').get(order__public_id=order_id)
        except Conversation.DoesNotExist:
            return {'error': 'Conversa não encontrada.'}
        except DatabaseError:
            return {'error': 'Não foi possível salvar a mensagem agora.'}

        if convo.closed:
            return {'error': 'Conversa encerrada.'}

        try:
            msg = Message.objects.create(conversation=convo, sender_id=user_id, body=text)
        except DatabaseError:
            return {'error': 'Não foi possível salvar a mensagem agora.'}

        return {
            'id': msg.id,
            'message': msg.body,
            'sender_id': user_id,
            'created_at': msg.created_at.isoformat(),
        }
