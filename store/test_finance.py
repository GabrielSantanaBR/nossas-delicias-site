from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CafeAccount, Category, DeliveryRegion, Order, PriceTable, Product, ProductPrice
from .financial_models import CafeDeliveryNote, ProductCostProfile
from .financial_services import (
    cafe_cutoff,
    cafe_order_editable,
    lock_cafe_note,
    refresh_order_financials,
    sales_report,
)


class FinanceFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cafe', 'cafe@example.com', 'StrongPassword123!')
        self.other = User.objects.create_user('other', 'other@example.com', 'StrongPassword123!')
        self.cafe_table = PriceTable.objects.create(name='Cafeterias', kind='cafe', active=True)
        CafeAccount.objects.create(
            user=self.user,
            business_name='Café Teste',
            approved=True,
            active=True,
            minimum_order=Decimal('0'),
            price_table=self.cafe_table,
        )
        CafeAccount.objects.create(
            user=self.other,
            business_name='Outro Café',
            approved=True,
            active=True,
            minimum_order=Decimal('0'),
            price_table=self.cafe_table,
        )
        self.category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(
            category=self.category,
            name='Brownie Teste',
            slug='brownie-teste',
            description='Produto de teste',
            image='products/test.jpg',
            sell_cafe=True,
        )
        ProductPrice.objects.create(product=self.product, table=self.cafe_table, min_quantity=1, unit_price=Decimal('20.00'))
        self.cost = ProductCostProfile.objects.create(
            product=self.product,
            sku='REC-TEST',
            sale_unit='unit',
            yield_quantity=Decimal('1'),
            production_cost=Decimal('10.00'),
        )
        self.region = DeliveryRegion.objects.create(name='Rota Teste', delivery_fee=Decimal('0'), minimum_order=Decimal('0'), zip_prefixes='21')
        self.delivery = timezone.localdate() + timedelta(days=2)
        self.order = Order.objects.create(
            customer=self.user,
            order_type='cafe',
            status='paid',
            delivery_date=self.delivery,
            delivery_region=self.region,
            subtotal=Decimal('40.00'),
            total=Decimal('40.00'),
        )
        self.item = self.order.items.create(product=self.product, quantity=2, unit_price=Decimal('20.00'))

    def test_cafe_order_is_editable_before_cutoff_and_frozen_at_16(self):
        cutoff = cafe_cutoff(self.order)
        self.assertTrue(cafe_order_editable(self.order, at=cutoff - timedelta(seconds=1)))
        self.assertFalse(cafe_order_editable(self.order, at=cutoff))
        self.assertFalse(cafe_order_editable(self.order, at=cutoff + timedelta(minutes=1)))

    def test_locked_note_preserves_historical_cost_after_recipe_cost_changes(self):
        refresh_order_financials(self.order)
        note = CafeDeliveryNote.objects.get(order=self.order)
        lock_cafe_note(note, force=True)

        snapshot = self.item.financial_snapshot
        self.assertEqual(snapshot.unit_cost, Decimal('10.0000'))
        self.assertEqual(snapshot.revenue, Decimal('40.00'))
        self.assertEqual(snapshot.total_cost, Decimal('20.00'))
        self.assertEqual(snapshot.profit, Decimal('20.00'))
        self.assertEqual(snapshot.margin_percent, Decimal('50.00'))

        self.cost.production_cost = Decimal('15.00')
        self.cost.save()
        refresh_order_financials(self.order)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.unit_cost, Decimal('10.0000'))
        self.assertEqual(snapshot.profit, Decimal('20.00'))

    def test_sales_report_matches_spreadsheet_style_totals(self):
        refresh_order_financials(self.order)
        report = sales_report(self.delivery, self.delivery, order_type='cafe')
        self.assertEqual(report['totals']['items'], 2)
        self.assertEqual(report['totals']['revenue'], Decimal('40.00'))
        self.assertEqual(report['totals']['cost'], Decimal('20.00'))
        self.assertEqual(report['totals']['profit'], Decimal('20.00'))
        self.assertEqual(report['totals']['margin_percent'], Decimal('50.00'))
        self.assertEqual(report['totals']['order_count'], 1)

    def test_one_cafe_cannot_open_another_cafes_note_editor(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('cafe_order_edit', kwargs={'public_id': self.order.public_id}))
        self.assertEqual(response.status_code, 404)

    def test_unverified_staff_cannot_open_finance_dashboard(self):
        staff = User.objects.create_user('staff', 'staff@example.com', 'StrongPassword123!', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('finance_dashboard'))
        self.assertEqual(response.status_code, 403)
