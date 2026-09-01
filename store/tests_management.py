from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
from openpyxl import load_workbook

from .financial_models import ProductCostProfile
from .financial_services import refresh_order_financials
from .management_models import Ingredient, Recipe
from .models import CafeAccount, Order
from .spreadsheet_io import build_management_workbook


class SpreadsheetRoundTripTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manager', 'manager@example.com', 'StrongPassword-123!')
        self.product = self._create_product()

    def _create_product(self):
        from .models import Category, Product
        category = Category.objects.create(name='Testes', slug='testes')
        return Product.objects.create(
            category=category, name='Produto teste', slug='produto-teste', description='Teste',
            image='products/teste.jpg', active=True, featured=True,
        )

    def test_export_contains_management_sheets(self):
        Ingredient.objects.create(code='ING-001', name='Chocolate', package_price=30, package_quantity=500, base_unit='g')
        stream = build_management_workbook(timezone.localdate().replace(day=1), timezone.localdate())
        workbook = load_workbook(stream, read_only=True, data_only=True)
        expected = {'PAINEL', 'BASE DE PREÇOS', 'PRECIFICAÇÃO', 'RECEITAS', 'VENDAS CLIENTES', 'VENDAS CAFETERIAS', 'VENDAS EVENTOS', 'ANÁLISE DE VENDAS', 'DESPESAS', 'CUSTOS FIXOS', 'ESTOQUE', 'FLUXO DE CAIXA'}
        self.assertTrue(expected.issubset(set(workbook.sheetnames)))

    def test_export_creates_one_safe_sheet_for_every_cafe(self):
        first_user = User.objects.create_user('cafe-1', 'cafe1@example.com', 'StrongPassword-456!')
        second_user = User.objects.create_user('cafe-2', 'cafe2@example.com', 'StrongPassword-789!')
        first = CafeAccount.objects.create(user=first_user, business_name='Café / Zona Sul: Copacabana')
        CafeAccount.objects.create(user=second_user, business_name='Café / Zona Sul: Copacabana')
        order = Order.objects.create(
            customer=first.user, order_type='cafe', status='paid', delivery_date=timezone.localdate(),
            subtotal=Decimal('20.00'), total=Decimal('20.00'),
        )
        order.items.create(product=self.product, quantity=2, unit_price=Decimal('10.00'))
        refresh_order_financials(order)
        stream = build_management_workbook(timezone.localdate().replace(day=1), timezone.localdate())
        workbook = load_workbook(stream, read_only=True, data_only=True)
        cafe_sheets = [name for name in workbook.sheetnames if name.startswith('CAFÉ - ')]
        self.assertEqual(len(cafe_sheets), 2)
        self.assertEqual(len(set(name.casefold() for name in cafe_sheets)), 2)
        self.assertTrue(all(len(name) <= 31 and '/' not in name and ':' not in name for name in cafe_sheets))
        self.assertEqual(sum(workbook[name].max_row - 1 for name in cafe_sheets), 1)

    def test_management_center_requires_verified_admin(self):
        self.client.force_login(self.user)
        response = self.client.get('/gestao/')
        self.assertEqual(response.status_code, 403)

    def test_health_endpoint_checks_dependencies(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')


class NativeCatalogTests(TestCase):
    def test_native_catalog_is_complete_and_idempotent(self):
        call_command('load_native_catalog', verbosity=0)
        self.assertEqual(Ingredient.objects.count(), 80)
        self.assertEqual(Recipe.objects.count(), 64)
        self.assertEqual(Recipe.objects.count(), 64)
        self.assertEqual(Recipe.objects.get(code='REC-001').production_cost, Decimal('0.00'))
        incomplete = Recipe.objects.get(code='REC-021')
        self.assertTrue(incomplete.active)
        self.assertFalse(incomplete.ingredients.exists())
        call_command('load_native_catalog', verbosity=0)
        self.assertEqual((Ingredient.objects.count(), Recipe.objects.count()), (80, 64))
