from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import (
    AvailabilityDay,
    CafeAccount,
    Category,
    Conversation,
    DeliveryRegion,
    EventQuote,
    Message,
    Order,
    Product,
)


class OperationsWorkspaceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'ops-admin', 'ops@example.com', 'VeryStrongPassword-123!', is_staff=True
        )
        self.device = TOTPDevice.objects.create(user=self.admin, name='tests', confirmed=True)
        self.client.force_login(self.admin)
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = self.device.persistent_id
        session.save()

        self.customer = User.objects.create_user(
            'cliente', 'cliente@example.com', 'VeryStrongPassword-456!'
        )
        self.category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(
            category=self.category,
            name='Brownie Tradicional',
            slug='brownie-tradicional',
            description='Produto de teste',
            image='products/brownie.jpg',
            featured=True,
        )
        self.region = DeliveryRegion.objects.create(
            name='Rota teste', delivery_fee=Decimal('8.00'), minimum_order=Decimal('20.00')
        )
        self.order = Order.objects.create(
            customer=self.customer,
            order_type='retail',
            status='paid',
            delivery_date=timezone.localdate() + timedelta(days=2),
            delivery_region=self.region,
            subtotal=Decimal('30.00'),
            total=Decimal('38.00'),
        )
        self.order.items.create(product=self.product, quantity=3, unit_price=Decimal('10.00'))
        self.conversation = Conversation.objects.create(order=self.order, customer=self.customer)
        Message.objects.create(conversation=self.conversation, sender=self.customer, body='Mensagem nova')

    def test_management_workspace_renders_all_business_modules(self):
        response = self.client.get(reverse('management_center'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        for marker in (
            'Portfólio & site', 'Pedidos', 'Mensagens', 'Cafeterias', 'Eventos',
            'Logística', 'Dados & planilha', 'Financeiro', 'Precificação', 'Produção & estoque',
        ):
            self.assertIn(marker, body)

    def test_order_status_action_updates_history(self):
        response = self.client.post(reverse('management_order_status'), {
            'order_id': self.order.pk,
            'status': 'production',
        })
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'production')
        self.assertTrue(self.order.status_history.filter(status='production', changed_by=self.admin).exists())

    def test_management_reply_persists_and_marks_customer_messages_read(self):
        response = self.client.post(reverse('management_conversation_send'), {
            'conversation_id': self.conversation.pk,
            'body': 'Resposta da equipe',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender=self.admin,
                body='Resposta da equipe',
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                conversation=self.conversation,
                sender=self.customer,
                read_at__isnull=True,
            ).exists()
        )

    def test_cafe_can_be_approved_from_operations_workspace(self):
        cafe_user = User.objects.create_user(
            'cafe', 'cafe@example.com', 'VeryStrongPassword-789!'
        )
        cafe = CafeAccount.objects.create(
            user=cafe_user,
            business_name='Café Teste',
            approved=False,
            active=True,
        )
        response = self.client.post(reverse('management_cafe_action'), {
            'cafe_id': cafe.pk,
            'action': 'approve',
        })
        self.assertEqual(response.status_code, 302)
        cafe.refresh_from_db()
        self.assertTrue(cafe.approved)
        self.assertTrue(cafe.active)

    def test_event_status_can_advance_from_workspace(self):
        quote = EventQuote.objects.create(
            customer=self.customer,
            event_type='birthday',
            event_date=timezone.localdate() + timedelta(days=20),
            guest_count=60,
            status='new',
        )
        response = self.client.post(reverse('management_event_status'), {
            'quote_id': quote.pk,
            'status': 'review',
        })
        self.assertEqual(response.status_code, 302)
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'review')

    def test_logistics_day_can_be_blocked_and_released(self):
        date = timezone.localdate() + timedelta(days=4)
        response = self.client.post(reverse('management_availability_save'), {
            'date': date.isoformat(),
            'capacity': '24',
            'enabled': '0',
            'note': 'Produção fechada',
        })
        self.assertEqual(response.status_code, 302)
        day = AvailabilityDay.objects.get(date=date)
        self.assertFalse(day.enabled)
        self.assertEqual(day.capacity, 24)
        self.assertEqual(day.note, 'Produção fechada')
