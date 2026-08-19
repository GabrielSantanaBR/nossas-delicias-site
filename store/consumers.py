from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversation, Message

class OrderChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user=self.scope['user']; self.order_id=self.scope['url_route']['kwargs']['order_id']
        if not user.is_authenticated or not await self.can_access(user.id,self.order_id):
            await self.close(code=4403); return
        self.group=f'order_chat_{self.order_id}'
        await self.channel_layer.group_add(self.group,self.channel_name); await self.accept()

    async def disconnect(self,code):
        if hasattr(self,'group'): await self.channel_layer.group_discard(self.group,self.channel_name)

    async def receive_json(self,content,**kwargs):
        text=(content.get('message') or '').strip()
        if not text or len(text)>4000: return
        payload=await self.save_message(self.scope['user'].id,self.order_id,text)
        await self.channel_layer.group_send(self.group,{'type':'chat.message','payload':payload})

    async def chat_message(self,event): await self.send_json(event['payload'])

    @database_sync_to_async
    def can_access(self,user_id,order_id):
        return Conversation.objects.filter(order__public_id=order_id).filter(customer_id=user_id).exists() or self.scope['user'].is_staff

    @database_sync_to_async
    def save_message(self,user_id,order_id,text):
        convo=Conversation.objects.get(order__public_id=order_id)
        if convo.closed: return {'error':'Conversa encerrada.'}
        msg=Message.objects.create(conversation=convo,sender_id=user_id,body=text)
        return {'id':msg.id,'message':msg.body,'sender_id':user_id,'created_at':msg.created_at.isoformat()}
