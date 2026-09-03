from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .consumers import can_user_access_order_chat, consume_shared_chat_quota
from .models import Conversation, Order


class OrderChatSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('chat-owner', password='VeryStrongPassword-123!')
        self.other = User.objects.create_user('chat-other', password='VeryStrongPassword-456!')
        self.order = Order.objects.create(customer=self.owner, total=Decimal('20.00'))
        Conversation.objects.create(order=self.order, customer=self.owner)

    def test_only_order_owner_can_open_public_chat(self):
        self.assertTrue(can_user_access_order_chat(self.owner.pk, self.order.public_id))
        self.assertFalse(can_user_access_order_chat(self.other.pk, self.order.public_id))

    def test_shared_rate_limit_survives_connection_restarts(self):
        kwargs = {
            'user_id': self.owner.pk,
            'order_id': self.order.public_id,
            'limit': 3,
            'window_seconds': 10,
            'now': 100,
        }
        self.assertTrue(consume_shared_chat_quota(**kwargs))
        self.assertTrue(consume_shared_chat_quota(**kwargs))
        self.assertTrue(consume_shared_chat_quota(**kwargs))
        self.assertFalse(consume_shared_chat_quota(**kwargs))

        # A different account has a separate quota, while a new window resets it.
        self.assertTrue(consume_shared_chat_quota(**{**kwargs, 'user_id': self.other.pk}))
        self.assertTrue(consume_shared_chat_quota(**{**kwargs, 'now': 110}))
