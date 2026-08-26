import io
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from .financial_models import ProductCostProfile
from .management_models import FinancialSettings, FixedCost, Ingredient, InventoryMovement, Recipe, RecipeIngredient
from .management_services import simulate_price, sync_recipe_product_cost
from .models import Category, Product, ProductPrice
from .spreadsheet_io import build_management_workbook, import_management_workbook


class ManagementCalculationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(
            category=self.category,
            name='Brownie Tradicional',
            slug='brownie-tradicional',
            description='Teste',
            image='products/brownie.jpg',
        )

    def test_ingredient_unit_cost_and_stock_movement(self):
        ingredient = Ingredient.objects.create(
            code='ING-001', name='Chocolate 100%', package_price=Decimal('30.00'),
            package_quantity=Decimal('500'), base_unit='g', minimum_stock=Decimal('100'),
        )
        self.assertEqual(ingredient.unit_cost, Decimal('0.060000'))
        InventoryMovement.objects.create(ingredient=ingredient, movement_type='purchase', quantity_delta=Decimal('1000'))
        InventoryMovement.objects.create(ingredient=ingredient, movement_type='production', quantity_delta=Decimal('250'))
        self.assertEqual(ingredient.stock_balance, Decimal('750.0000'))

    def test_recipe_cost_uses_current_ingredient_base_and_syncs_product_profile(self):
        ingredient = Ingredient.objects.create(
            code='ING-001', name='Chocolate 100%', package_price=Decimal('30.00'),
            package_quantity=Decimal('500'), base_unit='g',
        )
        recipe = Recipe.objects.create(
            code='REC-001', name='Brownie Tradicional', category='Brownies', sale_unit='unit',
            yield_quantity=Decimal('10'), extra_cost=Decimal('5.00'), product=self.product,
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity_used=Decimal('500'))
        self.assertEqual(recipe.production_cost, Decimal('35.0000'))
        self.assertEqual(recipe.unit_cost, Decimal('3.5000'))
        sync_recipe_product_cost(recipe)
        profile = ProductCostProfile.objects.get(product=self.product)
        self.assertEqual(profile.unit_cost, Decimal('3.5000'))

    def test_price_simulator_matches_margin_and_break_even_rules(self):
        settings = FinancialSettings.current()
        settings.desired_margin_percent = Decimal('30')
        settings.payment_fee_percent = Decimal('0')
        settings.tax_percent = Decimal('0')
        settings.contingency_percent = Decimal('0')
        settings.save()
        FixedCost.objects.create(name='Estrutura', monthly_amount=Decimal('290.00'), due_day=1)
        recipe = Recipe.objects.create(
            code='REC-002', name='Teste', category='Brownies', sale_unit='unit',
            yield_quantity=Decimal('10'), imported_production_cost=Decimal('70.00'),
        )
        result = simulate_price(recipe, current_price=Decimal('9.00'), desired_margin=Decimal('30'), increase_percent=Decimal('10'), quantity=100)
        self.assertEqual(result['recommended_price'], Decimal('10.00'))
        self.assertEqual(result['new_price'], Decimal('9.90'))
        self.assertEqual(result['extra_total'], Decimal('90.00'))
        self.assertEqual(result['break_even_units'], 100)
        self.assertEqual(result['break_even_revenue'], Decimal('990.00'))


class SpreadsheetRoundTripTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('gestor', 'gestor@example.com', 'StrongPassword-123!', is_staff=True)
        category = Category.objects.create(name='Brownies', slug='brownies')
        self.product = Product.objects.create(
            category=category, name='Brownie Tradicional', slug='brownie-tradicional',
            description='Teste', image='products/brownie.jpg',
        )
        ProductCostProfile.objects.create(
            product=self.product, sku='REC-001', sale_unit='unit', yield_quantity=10,
            production_cost=Decimal('40.00'), source_reference='Teste',
        )

    def _upload(self):
        wb = Workbook()
        base = wb.active
        base.title = 'BASE DE PREÇOS'
        base.append(['Código', 'Ingrediente padrão', 'Categoria', 'Preço da embalagem', 'Qtd. da embalagem', 'Unidade base', 'Status', 'Fornecedor', 'Observações', 'Nomes encontrados'])
        base.append(['ING-001', 'CHOCOLATE 100%', 'Chocolates e cacau', 'R$ 30,00', '500', 'g', 'ATIVO', 'Fornecedor teste', 'Base', 'CACAU | CACAU 100%'])
        pricing = wb.create_sheet('PRECIFICAÇÃO')
        pricing.append(['MARGEM DESEJADA', 0.30])
        pricing.append([])
        pricing.append(['Código', 'Categoria', 'Produto', 'Unidade de venda', 'Rendimento (qtd.)', 'Custo total', 'Custo unitário', 'Preço cafeteria', 'Preço cliente', 'Preço recomendado', 'Situação', 'Venda ativa?'])
        pricing.append(['REC-001', 'BROWNIE', 'Brownie Tradicional', 'UNIDADE', 10, 50, 5, 7, 10, 8, 'OK', 'SIM'])
        stream = io.BytesIO()
        wb.save(stream)
        return SimpleUploadedFile('Planilha Automatizada 4.0.xlsx', stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_import_updates_ingredient_recipe_margin_and_linked_prices(self):
        result = import_management_workbook(self._upload(), user=self.user)
        ingredient = Ingredient.objects.get(code='ING-001')
        recipe = Recipe.objects.get(code='REC-001')
        self.assertEqual(ingredient.package_price, Decimal('30.00'))
        self.assertEqual(ingredient.unit_cost, Decimal('0.060000'))
        self.assertEqual(recipe.imported_production_cost, Decimal('50'))
        self.assertEqual(recipe.sale_unit, 'unit')
        self.assertEqual(recipe.product, self.product)
        self.assertEqual(FinancialSettings.current().desired_margin_percent, Decimal('30.00'))
        self.assertEqual(ProductPrice.objects.get(product=self.product, table__kind='cafe').unit_price, Decimal('7'))
        self.assertEqual(ProductPrice.objects.get(product=self.product, table__kind='retail').unit_price, Decimal('10'))
        self.assertEqual(result['prices_updated'], 2)

    def test_invalid_xlsx_is_rejected_before_openpyxl_processing(self):
        invalid = SimpleUploadedFile('planilha.xlsx', b'not-a-zip', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with self.assertRaises(ValueError):
            import_management_workbook(invalid, user=self.user)

    def test_export_contains_management_sheets(self):
        Ingredient.objects.create(code='ING-001', name='Chocolate', package_price=30, package_quantity=500, base_unit='g')
        stream = build_management_workbook(timezone.localdate().replace(day=1), timezone.localdate())
        workbook = load_workbook(stream, read_only=True, data_only=True)
        expected = {'PAINEL', 'BASE DE PREÇOS', 'PRECIFICAÇÃO', 'VENDAS CLIENTES', 'VENDAS CAFETERIAS', 'VENDAS EVENTOS', 'ANÁLISE DE VENDAS', 'DESPESAS', 'CUSTOS FIXOS', 'ESTOQUE', 'FLUXO DE CAIXA'}
        self.assertTrue(expected.issubset(set(workbook.sheetnames)))

    def test_management_center_requires_verified_admin(self):
        self.client.force_login(self.user)
        response = self.client.get('/gestao/')
        self.assertEqual(response.status_code, 403)

    def test_health_endpoint_checks_dependencies(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
