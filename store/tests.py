from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from .forms import EventQuoteForm
from .models import (
    CafeAccount,
    Category,
    CustomerProfile,
    DeliveryRegion,
    DeliveryRoute,
    Order,
    PriceTable,
    Product,
    ProductPrice,
)
from .payment_gateway import create_checkout_preference
from .services import can_schedule, lock_delivery_slot, price_for, region_for_zip


class CommerceServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cliente', 'cliente@example.com', 'StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user)
        self.category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(
            category=self.category,
            name='Brownie',
            slug='brownie',
            description='Teste',
            image='products/test.jpg',
        )
        self.table = PriceTable.objects.create(name='Varejo', kind='retail')
        ProductPrice.objects.create(product=self.product, table=self.table, min_quantity=1, unit_price=Decimal('8.00'))
        ProductPrice.objects.create(product=self.product, table=self.table, min_quantity=10, unit_price=Decimal('6.50'))
        self.region = DeliveryRegion.objects.create(
            name='Guadalupe',
            delivery_fee=Decimal('5.00'),
            minimum_order=Decimal('20.00'),
            zip_prefixes='21660,21665',
        )

    def test_quantity_tier_price(self):
        self.assertEqual(price_for(self.user, self.product, 1, 'retail'), Decimal('8.00'))
        self.assertEqual(price_for(self.user, self.product, 10, 'retail'), Decimal('6.50'))

    def test_zip_region(self):
        self.assertEqual(region_for_zip('21660-000').name, 'Guadalupe')
        self.assertIsNone(region_for_zip('20000-000'))

    def test_customer_cannot_open_another_users_order(self):
        other = User.objects.create_user('outro', 'outro@example.com', 'StrongPassword-123!')
        order = Order.objects.create(customer=other, total=Decimal('10.00'))
        self.client.login(username='cliente', password='StrongPassword-123!')
        response = self.client.get(f'/pedidos/{order.public_id}/')
        self.assertEqual(response.status_code, 404)

    def test_security_headers_are_present(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['X-Permitted-Cross-Domain-Policies'], 'none')

    def test_event_quote_rejects_past_date(self):
        form = EventQuoteForm(data={
            'event_type': 'birthday',
            'event_date': timezone.localdate() - timedelta(days=1),
            'guest_count': 20,
            'address': 'Rio de Janeiro',
            'notes': 'Teste',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('event_date', form.errors)

    def test_cafe_catalog_hides_retail_only_product(self):
        cafe_user = User.objects.create_user('cafe', 'cafe@example.com', 'StrongPassword-123!')
        CustomerProfile.objects.create(user=cafe_user, customer_type='cafe')
        CafeAccount.objects.create(user=cafe_user, business_name='Café Teste', approved=True, active=True)
        retail_only = Product.objects.create(
            category=self.category,
            name='Somente varejo',
            slug='somente-varejo',
            description='Não deve aparecer para cafeteria',
            image='products/retail.jpg',
            sell_retail=True,
            sell_cafe=False,
        )
        ProductPrice.objects.create(product=retail_only, table=self.table, min_quantity=1, unit_price=Decimal('9.00'))
        self.client.login(username='cafe', password='StrongPassword-123!')
        response = self.client.get('/cardapio/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Somente varejo')

    def test_old_pending_payment_does_not_hold_delivery_capacity_forever(self):
        delivery_date = timezone.localdate() + timedelta(days=1)
        route = DeliveryRoute.objects.create(
            name='Rota teste',
            active=True,
            weekdays=str(delivery_date.weekday()),
            default_capacity=1,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        route.regions.add(self.region)
        stale = Order.objects.create(
            customer=self.user,
            order_type='retail',
            status='pending_payment',
            delivery_date=delivery_date,
            delivery_region=self.region,
            total=Decimal('20.00'),
        )
        Order.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=2))
        self.assertTrue(can_schedule(self.region, delivery_date, lead_days=1))


class TransactionBoundaryTests(TransactionTestCase):
    reset_sequences = True

    def test_lock_delivery_slot_requires_atomic_transaction(self):
        region = DeliveryRegion.objects.create(name='Teste', zip_prefixes='20000')
        delivery_date = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(RuntimeError):
            lock_delivery_slot(region, delivery_date, 1)


class PaymentGatewayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pagador', 'pagador@example.com', 'StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user)
        category = Category.objects.create(name='Doces', slug='doces')
        product = Product.objects.create(
            category=category,
            name='Caixa doce',
            slug='caixa-doce',
            description='Teste',
            image='products/doces.jpg',
        )
        self.order = Order.objects.create(
            customer=self.user,
            order_type='retail',
            status='pending_payment',
            subtotal=Decimal('100.00'),
            discount=Decimal('15.00'),
            delivery_fee=Decimal('7.00'),
            total=Decimal('92.00'),
        )
        self.order.items.create(product=product, quantity=2, unit_price=Decimal('50.00'))

    @patch('store.payment_gateway.sdk')
    def test_checkout_uses_authoritative_order_total_after_discount(self, mocked_sdk):
        preference_api = MagicMock()
        preference_api.create.return_value = {
            'status': 201,
            'response': {'id': 'pref-123', 'init_point': 'https://example.com/pay'},
        }
        mocked_sdk.return_value.preference.return_value = preference_api
        request = RequestFactory().post('/pedidos/pagar/', HTTP_HOST='testserver')
        result = create_checkout_preference(request, self.order)
        payload = preference_api.create.call_args.args[0]
        self.assertEqual(payload['items'][0]['unit_price'], 92.0)
        self.assertEqual(payload['external_reference'], str(self.order.public_id))
        self.assertEqual(result['id'], 'pref-123')
