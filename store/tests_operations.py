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
    EventQuoteItem,
    Message,
    Order,
    Payment,
    Product,
    ProductPrice,
)
from .financial_models import ProductCostProfile


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
            'Logística', 'Dados & relatórios', 'Financeiro', 'Precificação', 'Produção & estoque',
        ):
            self.assertIn(marker, body)
        self.assertNotIn('Importar planilha', body)

    def test_pricing_simulator_is_a_complete_management_screen(self):
        response = self.client.get(reverse('pricing_simulator'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Teste o preço antes de mudar o cardápio.')
        self.assertContains(response, 'Parâmetros da simulação')

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

    def test_message_thread_loads_on_demand_and_marks_incoming_as_read(self):
        response = self.client.get(reverse('management_conversation_thread', args=[self.conversation.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['conversation_id'], self.conversation.pk)
        self.assertEqual(payload['messages'][0]['body'], 'Mensagem nova')
        self.assertFalse(payload['messages'][0]['from_team'])
        self.assertFalse(self.conversation.messages.filter(read_at__isnull=True).exists())

    def test_management_reply_supports_ajax_without_page_reload(self):
        response = self.client.post(reverse('management_conversation_send'), {
            'conversation_id': self.conversation.pk,
            'body': 'Resposta instantânea',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message']['body'], 'Resposta instantânea')
        self.assertTrue(response.json()['message']['from_team'])

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
        self.assertTrue(quote.status_history.filter(status='review', changed_by=self.admin).exists())

    def test_accepted_event_converts_to_authoritative_order(self):
        quote = EventQuote.objects.create(
            customer=self.customer,
            event_type='birthday',
            event_date=timezone.localdate() + timedelta(days=20),
            guest_count=60,
            address='Salão teste',
            status='accepted',
        )
        EventQuoteItem.objects.create(
            quote=quote,
            product=self.product,
            description='Mesa de brownies',
            quantity=20,
            proposed_unit_price=Decimal('7.50'),
        )
        response = self.client.post(reverse('management_event_convert'), {'quote_id': quote.pk})
        self.assertEqual(response.status_code, 302)
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'converted')
        self.assertEqual(quote.final_total, Decimal('150.00'))
        self.assertEqual(quote.converted_order.order_type, 'event')
        self.assertEqual(quote.converted_order.total, Decimal('150.00'))
        self.assertTrue(hasattr(quote.converted_order, 'conversation'))
        self.assertTrue(quote.converted_order.items.get().financial_snapshot)

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

    def test_management_can_create_product_with_prices_and_cost(self):
        response = self.client.post(reverse('management_product_save'), {
            'category': self.category.pk,
            'name': 'Brownie de Café',
            'description': 'Brownie intenso com café e chocolate meio amargo.',
            'active': 'on',
            'featured': 'on',
            'sell_retail': 'on',
            'sell_event': 'on',
            'min_quantity': 4,
            'lead_time_days': 2,
            'sku': 'BR-CAFE-01',
            'sale_unit': 'unit',
            'production_cost': '24.00',
            'yield_quantity': 8,
            'retail_price': '8.50',
            'event_price': '7.50',
        })
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(slug='brownie-de-cafe')
        self.assertTrue(product.featured)
        self.assertEqual(product.cost_profile.unit_cost, Decimal('3.0000'))
        self.assertEqual(ProductPrice.objects.get(product=product, table__kind='retail').unit_price, Decimal('8.50'))
        self.assertEqual(ProductPrice.objects.get(product=product, table__kind='event').unit_price, Decimal('7.50'))

    def test_direct_sale_updates_payment_stock_and_profit(self):
        self.product.stock_limit = 10
        self.product.save(update_fields=['stock_limit', 'updated_at'])
        ProductCostProfile.objects.create(
            product=self.product,
            sku='BR-DIRECT',
            production_cost=Decimal('5.00'),
            yield_quantity=1,
        )
        response = self.client.post(reverse('management_direct_sale'), {
            'customer': self.customer.pk,
            'order_type': 'retail',
            'product': self.product.pk,
            'quantity': 2,
            'unit_price': '12.50',
            'sale_date': timezone.localdate().isoformat(),
            'payment_status': 'approved',
            'payment_method': 'pix',
            'note': 'Venda pelo WhatsApp',
        })
        self.assertEqual(response.status_code, 302)
        sale = Order.objects.filter(internal_note__contains='Venda direta').get()
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.total, Decimal('25.00'))
        self.assertTrue(Payment.objects.filter(order=sale, provider='manual', status='approved').exists())
        self.assertEqual(sale.items.get().financial_snapshot.profit, Decimal('15.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_limit, 8)

    def test_direct_sale_can_register_a_new_customer(self):
        response = self.client.post(reverse('management_direct_sale'), {
            'customer': '',
            'customer_name': 'Cliente do WhatsApp',
            'customer_email': 'novo.whatsapp@example.com',
            'order_type': 'retail',
            'product': self.product.pk,
            'quantity': 1,
            'unit_price': '10.00',
            'sale_date': timezone.localdate().isoformat(),
            'payment_status': 'pending',
            'payment_method': 'pix',
        })
        self.assertEqual(response.status_code, 302)
        customer = User.objects.get(email='novo.whatsapp@example.com')
        self.assertFalse(customer.has_usable_password())
        sale = customer.orders.get(internal_note__contains='Venda direta')
        self.assertEqual(sale.status, 'pending_payment')
        self.assertTrue(sale.payments.filter(status='pending', method='pix').exists())

    def test_direct_cafe_sale_requires_approved_business_account(self):
        response = self.client.post(reverse('management_direct_sale'), {
            'customer': self.customer.pk,
            'order_type': 'cafe',
            'product': self.product.pk,
            'quantity': 1,
            'unit_price': '10.00',
            'sale_date': timezone.localdate().isoformat(),
            'payment_status': 'approved',
            'payment_method': 'pix',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(internal_note__contains='Venda direta').exists())
