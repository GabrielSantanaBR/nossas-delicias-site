from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import CafeAccount, DeliveryRegion, DeliveryRoute, Order, PriceTable, Product, ProductPrice, Category, CustomerProfile
from .services import RETAIL_DAILY_CAPACITY, can_schedule, customer_order_type, price_for, route_for


class CafeAuthorizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('candidate', password='StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user, customer_type='cafe')
        self.cafe_table = PriceTable.objects.create(name='B2B', kind='cafe')
        self.retail_table = PriceTable.objects.create(name='Retail', kind='retail')
        category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(category=category, name='Brownie', slug='brownie', description='Teste', image='products/test.jpg', sell_retail=True, sell_cafe=True)
        ProductPrice.objects.create(product=self.product, table=self.retail_table, unit_price=Decimal('10.00'))
        ProductPrice.objects.create(product=self.product, table=self.cafe_table, unit_price=Decimal('7.00'))
        self.account = CafeAccount.objects.create(user=self.user, business_name='Café candidato', approved=False, active=True, price_table=None)

    def test_pending_cafe_stays_retail_and_does_not_receive_b2b_price(self):
        self.assertEqual(customer_order_type(self.user), 'retail')
        self.assertEqual(price_for(self.user, self.product), Decimal('10.00'))

    def test_approved_cafe_receives_b2b_channel_and_price(self):
        self.account.approved = True
        self.account.price_table = self.cafe_table
        self.account.save()
        self.assertEqual(customer_order_type(self.user), 'cafe')
        self.assertEqual(price_for(self.user, self.product), Decimal('7.00'))


class DeliveryRulesTests(TestCase):
    def setUp(self):
        self.nilopolis = DeliveryRegion.objects.create(name='Nilópolis — Clientes', zip_prefixes='265')
        self.center = DeliveryRegion.objects.create(name='Centro — Cafeterias', zip_prefixes='200')
        retail = DeliveryRoute.objects.create(name='Clientes | Nilópolis + Zona Oeste', weekdays='0,1,2,3,4,5', default_capacity=5, start_time=time(10), end_time=time(18))
        retail.regions.add(self.nilopolis)
        cafe = DeliveryRoute.objects.create(name='Cafeterias | Centro + Zona Sul', weekdays='1,3,4', default_capacity=24, start_time=time(8), end_time=time(14))
        cafe.regions.add(self.center)

    def _future_day(self, weekdays, minimum_days=7):
        current = timezone.localdate() + timedelta(days=minimum_days)
        while current.weekday() not in weekdays:
            current += timedelta(days=1)
        return current

    def test_routes_are_separated_by_channel(self):
        cafe_day = self._future_day({1, 3, 4})
        self.assertIsNone(route_for(self.center, cafe_day, order_type='retail'))
        self.assertIsNotNone(route_for(self.center, cafe_day, order_type='cafe'))

    def test_retail_requires_seven_days_and_has_global_five_order_limit(self):
        valid_day = self._future_day({0, 1, 2, 3, 4, 5})
        too_soon = timezone.localdate() + timedelta(days=2)
        self.assertFalse(can_schedule(self.nilopolis, too_soon, lead_days=1, order_type='retail'))
        self.assertTrue(can_schedule(self.nilopolis, valid_day, lead_days=1, order_type='retail'))

        user = User.objects.create_user('retail-demo')
        for _ in range(RETAIL_DAILY_CAPACITY):
            Order.objects.create(customer=user, order_type='retail', status='completed', delivery_date=valid_day, delivery_region=self.nilopolis)
        self.assertFalse(can_schedule(self.nilopolis, valid_day, lead_days=7, order_type='retail'))


class DemoSeedTests(TestCase):
    def test_seed_populates_operational_history(self):
        year = timezone.localdate().year
        call_command('seed_nossas_delicias_demo', year=year, verbosity=0)
        self.assertEqual(CafeAccount.objects.filter(approved=True, active=True, user__username__startswith='demo_cafe_').count(), 6)
        self.assertEqual(CafeAccount.objects.filter(approved=False, user__username='demo_cafe_pendente').count(), 1)
        self.assertGreaterEqual(Product.objects.filter(active=True, sell_retail=True, sell_cafe=True).count(), 8)
        cafe_orders = Order.objects.filter(order_type='cafe', delivery_date__year=year, delivery_date__month=8)
        self.assertGreater(cafe_orders.count(), 6)
        self.assertFalse(cafe_orders.exclude(delivery_date__week_day__in=[3, 5, 6]).exists())
        retail_by_day = {}
        for order in Order.objects.filter(order_type='retail', delivery_date__year=year, delivery_date__month=8):
            retail_by_day[order.delivery_date] = retail_by_day.get(order.delivery_date, 0) + 1
        self.assertTrue(retail_by_day)
        self.assertLessEqual(max(retail_by_day.values()), 5)
