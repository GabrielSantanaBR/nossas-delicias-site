import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from .models import Conversation, Message, Order


class OrderChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = int(self.scope["url_route"]["kwargs"]["order_id"])
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.can_access_order(user.id, self.order_id, user.is_staff):
            await self.close(code=4403)
            return

        self.group_name = f"order_chat_{self.order_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        body = str(payload.get("message", "")).strip()
        if not body or len(body) > 3000:
            return

        message = await self.save_message(self.scope["user"].id, self.order_id, body)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": message["body"],
                "sender": message["sender"],
                "created_at": message["created_at"],
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def can_access_order(self, user_id, order_id, is_staff):
        if is_staff:
            return Order.objects.filter(pk=order_id).exists()
        return Order.objects.filter(pk=order_id, customer_id=user_id).exists()

    @database_sync_to_async
    def save_message(self, user_id, order_id, body):
        order = Order.objects.get(pk=order_id)
        conversation, _ = Conversation.objects.get_or_create(order=order)
        message = Message.objects.create(conversation=conversation, sender_id=user_id, body=body)
        return {
            "body": message.body,
            "sender": message.sender.get_full_name() or message.sender.username,
            "created_at": message.created_at.isoformat(),
        }
