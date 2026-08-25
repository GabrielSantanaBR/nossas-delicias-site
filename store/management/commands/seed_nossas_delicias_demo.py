import calendar
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from store.financial_models import BusinessExpense, CafeDeliveryNote, Payment, ProductCostProfile
from store.financial_services import ensure_cafe_note, lock_cafe_note, refresh_order_financials
from store.management_models import FinancialSettings, FixedCost, Ingredient, InventoryMovement, Recipe
from store.models import (
    CafeAccount,
    Category,
    Conversation,
    CustomerAddress,
    CustomerProfile,
    DeliveryRegion,
    DeliveryRoute,
    EventQuote,
    EventQuoteItem,
    Message,
    Order,
    OrderItem,
    OrderStatusHistory,
    PriceTable,
    Product,
    ProductPrice,
    RecurringOrder,
    RecurringOrderItem,
)

DEMO_PREFIX = 'demo_'
DEMO_MARKER = '[DEMO]'


def aware_on(day, hour=10, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = 'Cria dados fictícios completos para demonstrar a operação da Nossas Delícias.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=timezone.localdate().year)
        parser.add_argument('--demo-password', default='', help='Senha opcional para todas as contas fictícias de cliente/cafeteria.')
        parser.add_argument('--admin-password', default='', help='Senha opcional para o usuário demo_admin.')
        parser.add_argument('--no-images', action='store_true', help='Não grava imagens-placeholder no storage.')

    @transaction.atomic
    def handle(self, *args, **options):
        year = options['year']
        demo_password = options['demo_password']
        admin_password = options['admin_password']
        no_images = options['no_images']
        today = timezone.localdate()

        self.stdout.write(self.style.MIGRATE_HEADING(f'Preparando demonstração operacional de agosto/{year}...'))
        self._cleanup_demo_transactions()
        admin = self._admin_user(admin_password)
        tables = self._price_tables()
        products = self._products(tables, no_images=no_images)
        self._financial_base(admin, products, year)
        regions = self._delivery_network()
        retail_users = self._retail_users(demo_password, regions)
        cafes = self._cafe_users(demo_password, tables['cafe'], regions)
        pending_cafe = self._pending_cafe(demo_password)
        self._seed_august_orders(year, today, retail_users, cafes, products, regions, admin)
        self._events(year, retail_users, products)
        self._messages(admin)
        self._refresh_customer_metrics()

        self.stdout.write(self.style.SUCCESS('Demonstração criada com sucesso.'))
        self.stdout.write('')
        self.stdout.write('Resumo:')
        self.stdout.write(f'  • {len(retail_users)} clientes fictícios')
        self.stdout.write(f'  • {len(cafes)} cafeterias aprovadas + 1 aguardando aprovação ({pending_cafe.business_name})')
        self.stdout.write(f'  • {len(products)} produtos com preço cliente e B2B')
        self.stdout.write('  • Clientes: Nilópolis + Zona Oeste, até 5 agendamentos/dia, antecedência mínima de 7 dias')
        self.stdout.write('  • Cafeterias: Centro + Zona Sul, entregas terça/quinta/sexta')
        self.stdout.write(f'  • Histórico operacional preenchido em agosto/{year}')
        self.stdout.write('  • Financeiro, estoque, despesas, eventos, conversas e notas B2B preenchidos')
        self.stdout.write('')
        self.stdout.write('Painel operacional: /gestao/')
        self.stdout.write('Admin avançado: /nd-admin/')
        if admin_password:
            self.stdout.write(self.style.WARNING('Usuário demo_admin recebeu a senha informada. Troque/remova essa conta antes de produção real.'))
        else:
            self.stdout.write('demo_admin foi criado sem senha utilizável. Use createsuperuser ou rode novamente com --admin-password apenas no ambiente de demo.')

    def _cleanup_demo_transactions(self):
        demo_orders = Order.objects.filter(customer__username__startswith=DEMO_PREFIX)
        Payment.objects.filter(order__in=demo_orders).delete()
        CafeDeliveryNote.objects.filter(order__in=demo_orders).delete()
        OrderStatusHistory.objects.filter(order__in=demo_orders).delete()
        demo_orders.delete()
        EventQuote.objects.filter(customer__username__startswith=DEMO_PREFIX).delete()
        BusinessExpense.objects.filter(description__startswith=DEMO_MARKER).delete()
        InventoryMovement.objects.filter(reference__startswith=DEMO_MARKER).delete()

    def _set_password(self, user, password):
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(update_fields=['password'])

    def _user(self, username, first_name, last_name, email, password='', staff=False, superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'is_staff': staff,
                'is_superuser': superuser,
                'is_active': True,
            },
        )
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_staff = staff
        user.is_superuser = superuser
        user.is_active = True
        user.save(update_fields=['first_name', 'last_name', 'email', 'is_staff', 'is_superuser', 'is_active'])
        if created or password:
            self._set_password(user, password)
        return user

    def _admin_user(self, password):
        return self._user(
            'demo_admin', 'Operação', 'Nossas Delícias', 'demo-admin@example.invalid',
            password=password, staff=True, superuser=True,
        )

    def _price_tables(self):
        retail, _ = PriceTable.objects.update_or_create(
            name='Clientes — Nossas Delícias',
            defaults={'kind': 'retail', 'active': True},
        )
        cafe, _ = PriceTable.objects.update_or_create(
            name='Cafeterias parceiras — B2B',
            defaults={'kind': 'cafe', 'active': True},
        )
        event, _ = PriceTable.objects.update_or_create(
            name='Eventos e encomendas especiais',
            defaults={'kind': 'event', 'active': True},
        )
        return {'retail': retail, 'cafe': cafe, 'event': event}

    def _placeholder_image(self, title, seed):
        palettes = [
            ((70, 35, 27), (210, 153, 122)),
            ((96, 49, 36), (236, 196, 173)),
            ((62, 37, 31), (197, 139, 111)),
            ((120, 70, 50), (243, 218, 194)),
            ((74, 43, 34), (223, 179, 154)),
        ]
        start, end = palettes[seed % len(palettes)]
        width, height = 1200, 900
        image = Image.new('RGB', (width, height), start)
        pixels = image.load()
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
            for x in range(width):
                pixels[x, y] = color
        draw = ImageDraw.Draw(image, 'RGBA')
        draw.ellipse((720, -140, 1240, 380), fill=(255, 248, 239, 36), outline=(255, 255, 255, 70), width=2)
        draw.ellipse((-180, 530, 430, 1140), fill=(45, 21, 15, 35))
        draw.rounded_rectangle((85, 610, 1115, 805), radius=38, fill=(30, 14, 10, 120), outline=(255, 255, 255, 55), width=2)
        draw.text((125, 660), 'NOSSAS DELICIAS', fill=(255, 239, 228, 255))
        draw.text((125, 710), title.upper()[:34], fill=(255, 255, 255, 255))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=88, optimize=True)
        return ContentFile(output.getvalue(), name=f'demo-{seed}.jpg')

    def _products(self, tables, no_images=False):
        categories = {}
        for order, (name, slug, description) in enumerate([
            ('Brownies', 'brownies', 'Brownies artesanais em diferentes sabores e acabamentos.'),
            ('Bolos & Fatias', 'bolos-fatias', 'Bolos e fatias para café, presente e sobremesa.'),
            ('Caixas & Presentes', 'caixas-presentes', 'Caixas prontas para presentear ou compartilhar.'),
        ]):
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'description': description, 'active': True, 'sort_order': order},
            )
            categories[slug] = category

        rows = [
            ('ND-BR-001', 'brownies', 'Brownie Tradicional', 'Chocolate intenso, centro úmido e casquinha delicada.', 'unit', '10.90', '7.20', '3.20'),
            ('ND-BR-002', 'brownies', 'Brownie Brigadeiro', 'Brownie de chocolate com cobertura cremosa de brigadeiro.', 'unit', '12.50', '8.10', '3.70'),
            ('ND-BR-003', 'brownies', 'Brownie Doce de Leite', 'Chocolate e doce de leite equilibrados em uma porção generosa.', 'unit', '12.50', '8.10', '3.65'),
            ('ND-BR-004', 'brownies', 'Brownie Ninho', 'Brownie artesanal com cobertura suave de leite em pó.', 'unit', '13.50', '8.70', '4.10'),
            ('ND-FT-001', 'bolos-fatias', 'Fatia Bolo de Chocolate', 'Fatia alta, massa macia e cobertura de chocolate.', 'slice', '14.90', '9.50', '4.40'),
            ('ND-FT-002', 'bolos-fatias', 'Fatia Bolo de Cenoura', 'Massa de cenoura com cobertura de chocolate.', 'slice', '13.90', '8.90', '4.00'),
            ('ND-CX-006', 'caixas-presentes', 'Caixa com 6 Brownies', 'Seleção de seis brownies para compartilhar ou presentear.', 'box', '62.00', '42.00', '19.00'),
            ('ND-CX-012', 'caixas-presentes', 'Caixa Presente com 12', 'Doze unidades em caixa presenteável para ocasiões especiais.', 'box', '118.00', '78.00', '38.00'),
        ]
        products = []
        for index, (sku, cat_slug, name, description, sale_unit, retail_price, cafe_price, unit_cost) in enumerate(rows):
            slug = name.lower().replace(' ', '-').replace('ã', 'a').replace('ç', 'c').replace('í', 'i')
            product, created = Product.objects.update_or_create(
                slug=slug,
                defaults={
                    'category': categories[cat_slug],
                    'name': name,
                    'description': description,
                    'active': True,
                    'featured': index < 6,
                    'sell_retail': True,
                    'sell_cafe': True,
                    'sell_event': False,
                    'min_quantity': 1,
                    'lead_time_days': 7,
                    'stock_limit': 500,
                    'sort_order': index,
                    'image': f'products/demo/{sku.lower()}.jpg',
                },
            )
            if not no_images and (created or not product.image.name or product.image.name.startswith('products/demo/')):
                try:
                    product.image.save(f'{sku.lower()}.jpg', self._placeholder_image(name, index), save=True)
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'Imagem demo de {name} não foi gravada: {exc}'))

            ProductPrice.objects.update_or_create(
                product=product, table=tables['retail'], min_quantity=1,
                defaults={'unit_price': money(retail_price)},
            )
            ProductPrice.objects.update_or_create(
                product=product, table=tables['cafe'], min_quantity=1,
                defaults={'unit_price': money(cafe_price)},
            )
            ProductCostProfile.objects.update_or_create(
                product=product,
                defaults={
                    'sku': sku,
                    'sale_unit': sale_unit,
                    'yield_quantity': Decimal('1'),
                    'production_cost': Decimal(unit_cost),
                    'source_reference': 'Demo operacional / referência Planilha 4.0',
                    'active': True,
                },
            )
            Recipe.objects.update_or_create(
                code=sku,
                defaults={
                    'name': name,
                    'category': categories[cat_slug].name,
                    'sale_unit': sale_unit,
                    'yield_quantity': Decimal('1'),
                    'imported_production_cost': Decimal(unit_cost),
                    'product': product,
                    'active': True,
                    'source_reference': 'Demo operacional',
                    'notes': 'Ficha de demonstração. Substituir pelos ingredientes reais antes de produção.',
                },
            )
            products.append(product)
        return products

    def _financial_base(self, admin, products, year):
        settings = FinancialSettings.current()
        settings.desired_margin_percent = Decimal('35.00')
        settings.payment_fee_percent = Decimal('4.50')
        settings.tax_percent = Decimal('0.00')
        settings.contingency_percent = Decimal('3.00')
        settings.save()

        for name, category, amount, due_day in [
            ('Estrutura de produção', 'rent', '700.00', 5),
            ('Água, luz, gás e internet', 'utilities', '260.00', 10),
            ('Sistemas e ferramentas', 'software', '120.00', 12),
            ('Reserva logística mensal', 'logistics', '350.00', 15),
        ]:
            FixedCost.objects.update_or_create(
                name=f'{DEMO_MARKER} {name}',
                defaults={
                    'category': category,
                    'monthly_amount': Decimal(amount),
                    'due_day': due_day,
                    'active': True,
                    'start_date': date(year, 1, 1),
                    'notes': 'Valor fictício para demonstração do painel.',
                },
            )

        for day, category, description, supplier, amount, status in [
            (2, 'ingredient', 'Compra de chocolate e cacau', 'Fornecedor Demo A', '860.00', 'paid'),
            (5, 'packaging', 'Embalagens e caixas', 'Fornecedor Demo B', '335.00', 'paid'),
            (9, 'logistics', 'Combustível e entregas', 'Operação própria', '475.00', 'paid'),
            (14, 'ingredient', 'Leite condensado, manteiga e secos', 'Fornecedor Demo C', '610.00', 'paid'),
            (18, 'marketing', 'Conteúdo e materiais de divulgação', 'Fornecedor Demo D', '190.00', 'paid'),
            (22, 'fees', 'Taxas e serviços financeiros', 'Serviços digitais', '128.00', 'paid'),
            (28, 'packaging', 'Reposição de caixas', 'Fornecedor Demo B', '280.00', 'pending'),
        ]:
            BusinessExpense.objects.create(
                date=date(year, 8, day),
                category=category,
                description=f'{DEMO_MARKER} {description}',
                supplier=supplier,
                amount=Decimal(amount),
                payment_status=status,
                payment_method='Pix' if status == 'paid' else '',
                notes='Despesa fictícia para demonstração.',
                created_by=admin,
            )

        ingredients = [
            ('ING-DEM-01', 'Chocolate 100%', 'Chocolates e cacau', '42.90', '1000', 'g', '8000', '1500'),
            ('ING-DEM-02', 'Farinha de trigo', 'Secos', '8.50', '1000', 'g', '9000', '1800'),
            ('ING-DEM-03', 'Açúcar', 'Secos', '6.90', '1000', 'g', '7500', '1500'),
            ('ING-DEM-04', 'Manteiga', 'Laticínios', '19.90', '500', 'g', '4200', '900'),
            ('ING-DEM-05', 'Ovos', 'Frescos', '18.00', '12', 'un', '180', '36'),
            ('ING-DEM-06', 'Leite condensado', 'Laticínios', '7.90', '395', 'g', '5200', '900'),
            ('ING-DEM-07', 'Embalagem brownie', 'Embalagens', '24.00', '100', 'un', '520', '100'),
            ('ING-DEM-08', 'Caixa presente', 'Embalagens', '39.00', '20', 'un', '90', '20'),
        ]
        for code, name, category, price, package_qty, unit, purchase_qty, minimum in ingredients:
            ingredient, _ = Ingredient.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': category,
                    'package_price': Decimal(price),
                    'package_quantity': Decimal(package_qty),
                    'base_unit': unit,
                    'supplier': 'Fornecedor fictício de demonstração',
                    'active': True,
                    'minimum_stock': Decimal(minimum),
                    'last_price_update': date(year, 8, 1),
                    'notes': 'Base fictícia para visualização do estoque.',
                },
            )
            InventoryMovement.objects.create(
                ingredient=ingredient,
                movement_type='purchase',
                quantity_delta=Decimal(purchase_qty),
                date=date(year, 8, 1),
                reference=f'{DEMO_MARKER} ESTOQUE INICIAL',
                notes='Entrada fictícia de demonstração.',
                created_by=admin,
            )
            consume = Decimal(purchase_qty) * Decimal('0.42')
            InventoryMovement.objects.create(
                ingredient=ingredient,
                movement_type='production',
                quantity_delta=consume,
                date=date(year, 8, 20),
                reference=f'{DEMO_MARKER} PRODUÇÃO AGOSTO',
                notes='Consumo acumulado fictício do mês.',
                created_by=admin,
            )

    def _delivery_network(self):
        nilopolis, _ = DeliveryRegion.objects.update_or_create(
            name='Nilópolis — Clientes',
            defaults={
                'active': True, 'delivery_fee': Decimal('9.00'), 'minimum_order': Decimal('35.00'),
                'zip_prefixes': '265,266',
            },
        )
        west, _ = DeliveryRegion.objects.update_or_create(
            name='Zona Oeste — Clientes',
            defaults={
                'active': True, 'delivery_fee': Decimal('14.00'), 'minimum_order': Decimal('45.00'),
                'zip_prefixes': '217,218,227,230,235',
            },
        )
        center, _ = DeliveryRegion.objects.update_or_create(
            name='Centro — Cafeterias',
            defaults={
                'active': True, 'delivery_fee': Decimal('0.00'), 'minimum_order': Decimal('120.00'),
                'zip_prefixes': '200,201,202',
            },
        )
        south, _ = DeliveryRegion.objects.update_or_create(
            name='Zona Sul — Cafeterias',
            defaults={
                'active': True, 'delivery_fee': Decimal('0.00'), 'minimum_order': Decimal('150.00'),
                'zip_prefixes': '220,222,224,226',
            },
        )

        retail_route, _ = DeliveryRoute.objects.update_or_create(
            name='Clientes | Nilópolis + Zona Oeste',
            defaults={
                'active': True,
                'weekdays': '0,1,2,3,4,5',
                'default_capacity': 5,
                'start_time': time(10, 0),
                'end_time': time(18, 0),
            },
        )
        retail_route.regions.set([nilopolis, west])

        cafe_route, _ = DeliveryRoute.objects.update_or_create(
            name='Cafeterias | Centro + Zona Sul',
            defaults={
                'active': True,
                'weekdays': '1,3,4',
                'default_capacity': 24,
                'start_time': time(8, 0),
                'end_time': time(14, 0),
            },
        )
        cafe_route.regions.set([center, south])
        return {'nilopolis': nilopolis, 'west': west, 'center': center, 'south': south}

    def _retail_users(self, password, regions):
        people = [
            ('demo_cliente_01', 'Marina', 'Alves'), ('demo_cliente_02', 'Lucas', 'Moura'),
            ('demo_cliente_03', 'Bianca', 'Silva'), ('demo_cliente_04', 'Rafael', 'Costa'),
            ('demo_cliente_05', 'Isabela', 'Rocha'), ('demo_cliente_06', 'Caio', 'Martins'),
            ('demo_cliente_07', 'Larissa', 'Souza'), ('demo_cliente_08', 'Pedro', 'Lima'),
            ('demo_cliente_09', 'Ana', 'Ferreira'), ('demo_cliente_10', 'Bruno', 'Carvalho'),
            ('demo_cliente_11', 'Julia', 'Ramos'), ('demo_cliente_12', 'Diego', 'Nunes'),
            ('demo_cliente_13', 'Camila', 'Duarte'), ('demo_cliente_14', 'Mateus', 'Pires'),
        ]
        users = []
        for index, (username, first, last) in enumerate(people):
            user = self._user(username, first, last, f'{username}@example.invalid', password=password)
            CustomerProfile.objects.update_or_create(
                user=user,
                defaults={
                    'customer_type': 'retail', 'phone': f'(21) 90000-{index + 1000:04d}',
                    'marketing_opt_in': index % 3 == 0,
                    'notes': 'Conta fictícia criada pelo seed operacional.',
                },
            )
            region = regions['nilopolis'] if index % 2 == 0 else regions['west']
            zip_code = '26510-100' if region == regions['nilopolis'] else '22775-100'
            CustomerAddress.objects.update_or_create(
                user=user, label='Principal',
                defaults={
                    'zip_code': zip_code,
                    'street': 'Rua Demonstração',
                    'number': str(100 + index),
                    'neighborhood': 'Bairro de demonstração',
                    'city': 'Rio de Janeiro' if region == regions['west'] else 'Nilópolis',
                    'default': True,
                },
            )
            users.append(user)
        return users

    def _cafe_users(self, password, cafe_table, regions):
        rows = [
            ('demo_cafe_01', 'Café Aurora Centro', 'Centro', '20040-020', 'center', 'Helena Prado', '150.00'),
            ('demo_cafe_02', 'Botafogo Doce Café', 'Botafogo', '22250-040', 'south', 'Miguel Torres', '160.00'),
            ('demo_cafe_03', 'Café Jardim Flamengo', 'Flamengo', '22220-030', 'south', 'Clara Reis', '150.00'),
            ('demo_cafe_04', 'Copacabana Grão & Afeto', 'Copacabana', '22040-010', 'south', 'Theo Campos', '180.00'),
            ('demo_cafe_05', 'Ipanema Café Estúdio', 'Ipanema', '22410-020', 'south', 'Lia Azevedo', '180.00'),
            ('demo_cafe_06', 'Leblon Ponto Doce', 'Leblon', '22440-030', 'south', 'Davi Freitas', '180.00'),
        ]
        cafes = []
        for index, (username, business, neighborhood, zip_code, region_key, contact, minimum) in enumerate(rows):
            user = self._user(username, contact.split()[0], contact.split()[-1], f'{username}@example.invalid', password=password)
            CustomerProfile.objects.update_or_create(
                user=user,
                defaults={
                    'customer_type': 'cafe', 'phone': f'(21) 91000-{index + 2000:04d}',
                    'marketing_opt_in': False,
                    'notes': 'Cafeteria fictícia aprovada para demonstração.',
                },
            )
            cafe, _ = CafeAccount.objects.update_or_create(
                user=user,
                defaults={
                    'business_name': business,
                    'contact_name': contact,
                    'approved': True,
                    'active': True,
                    'minimum_order': Decimal(minimum),
                    'price_table': cafe_table,
                    'internal_note': 'Cadastro B2B fictício. Conta autorizada para tabela de cafeteria.',
                },
            )
            CustomerAddress.objects.update_or_create(
                user=user, label='Cafeteria',
                defaults={
                    'zip_code': zip_code,
                    'street': 'Avenida Comercial Demo',
                    'number': str(20 + index),
                    'neighborhood': neighborhood,
                    'city': 'Rio de Janeiro',
                    'default': True,
                },
            )
            recurring, _ = RecurringOrder.objects.update_or_create(
                cafe=cafe, name='Reposição semanal',
                defaults={
                    'weekday': [1, 3, 4][index % 3],
                    'active': True,
                    'delivery_region': regions[region_key],
                    'delivery_address': f'Avenida Comercial Demo, {20 + index} — {neighborhood}',
                    'note': 'Reposição recorrente de demonstração.',
                },
            )
            cafes.append(cafe)
        return cafes

    def _pending_cafe(self, password):
        user = self._user('demo_cafe_pendente', 'Conta', 'Pendente', 'demo_cafe_pendente@example.invalid', password=password)
        CustomerProfile.objects.update_or_create(
            user=user,
            defaults={'customer_type': 'cafe', 'notes': 'Solicitação B2B fictícia aguardando autorização.'},
        )
        cafe, _ = CafeAccount.objects.update_or_create(
            user=user,
            defaults={
                'business_name': 'Café Horizonte — aguardando análise',
                'contact_name': 'Conta Pendente',
                'approved': False,
                'active': True,
                'minimum_order': Decimal('150.00'),
                'price_table': None,
                'internal_note': 'DEMO: não deve receber preço B2B nem rota de cafeteria antes da aprovação.',
            },
        )
        return cafe

    def _order(self, *, user, order_type, delivery_date, region, address, products, status, admin, paid=True, seed=0):
        table_kind = 'cafe' if order_type == 'cafe' else 'retail'
        line_rows = []
        subtotal = Decimal('0.00')
        for index, product in enumerate(products):
            price = ProductPrice.objects.filter(product=product, table__kind=table_kind, table__active=True).order_by('min_quantity').first().unit_price
            quantity = (6 + ((seed + index) % 8)) if order_type == 'cafe' else (1 + ((seed + index) % 3))
            if product.name.startswith('Caixa'):
                quantity = 1 if order_type == 'retail' else 2
            line_rows.append((product, quantity, price))
            subtotal += Decimal(price) * quantity
        fee = Decimal(region.delivery_fee)
        order = Order.objects.create(
            customer=user,
            order_type=order_type,
            status=status,
            delivery_date=delivery_date,
            delivery_region=region,
            delivery_address=address,
            delivery_fee=fee,
            subtotal=money(subtotal),
            discount=Decimal('0.00'),
            total=money(subtotal + fee),
            customer_note='Pedido fictício para demonstração do fluxo operacional.',
            internal_note=f'{DEMO_MARKER} histórico operacional agosto',
        )
        created_day = delivery_date - timedelta(days=8)
        Order.objects.filter(pk=order.pk).update(created_at=aware_on(created_day, 11, seed % 50))
        order.refresh_from_db()

        for product, quantity, price in line_rows:
            OrderItem.objects.create(order=order, product=product, quantity=quantity, unit_price=price, note='')
        OrderStatusHistory.objects.create(order=order, status='pending_payment', changed_by=user, note='Pedido fictício criado.')
        if status != 'pending_payment':
            OrderStatusHistory.objects.create(order=order, status=status, changed_by=admin, note='Atualização fictícia da operação.')

        conversation, _ = Conversation.objects.get_or_create(order=order, defaults={'customer': user})
        if seed % 5 == 0:
            Message.objects.create(conversation=conversation, sender=user, body='Olá! Só confirmando o horário aproximado da entrega.')

        if paid:
            Payment.objects.create(
                order=order,
                provider='demo',
                provider_id=f'demo-{order.public_id}',
                status='approved',
                amount=order.total,
                method='pix',
                paid_at=aware_on(created_day, 12, seed % 45),
                raw_reference={'source': 'seed_demo', 'fictional': True},
            )
        else:
            Payment.objects.create(
                order=order,
                provider='demo',
                provider_id=f'demo-{order.public_id}',
                status='pending',
                amount=order.total,
                method='pix',
                raw_reference={'source': 'seed_demo', 'fictional': True},
            )

        if order_type == 'cafe':
            refresh_order_financials(order, allow_locked=True)
            note = ensure_cafe_note(order)
            if delivery_date <= timezone.localdate():
                lock_cafe_note(note, user=admin, force=True)
        else:
            refresh_order_financials(order)
        return order

    def _seed_august_orders(self, year, today, retail_users, cafes, products, regions, admin):
        days = calendar.monthrange(year, 8)[1]
        cafe_index = 0
        retail_index = 0
        for day in range(1, days + 1):
            current = date(year, 8, day)

            if current.weekday() in {0, 1, 2, 3, 4, 5}:
                retail_count = 2 + (day % 2)
                for slot in range(retail_count):
                    user = retail_users[retail_index % len(retail_users)]
                    retail_index += 1
                    region = regions['nilopolis'] if (day + slot) % 2 == 0 else regions['west']
                    selected_products = [products[(day + slot) % 6], products[(day + slot + 2) % 6]]
                    if day % 6 == 0:
                        selected_products.append(products[6])
                    past_or_today = current <= today
                    status = 'completed' if past_or_today else ['paid', 'production', 'ready'][day % 3]
                    self._order(
                        user=user,
                        order_type='retail',
                        delivery_date=current,
                        region=region,
                        address=f'Rua Demonstração, {100 + retail_index} — {region.name}',
                        products=selected_products,
                        status=status,
                        admin=admin,
                        paid=past_or_today or day % 4 != 0,
                        seed=day * 10 + slot,
                    )

            if current.weekday() in {1, 3, 4}:
                for slot in range(2):
                    cafe = cafes[cafe_index % len(cafes)]
                    cafe_index += 1
                    address = cafe.user.saved_addresses.filter(default=True).first()
                    region = regions['center'] if 'Centro' in (address.neighborhood if address else '') else regions['south']
                    selected_products = [products[(day + slot) % 6], products[(day + slot + 1) % 6], products[6]]
                    past_or_today = current <= today
                    status = 'completed' if past_or_today else ['paid', 'production', 'ready'][day % 3]
                    self._order(
                        user=cafe.user,
                        order_type='cafe',
                        delivery_date=current,
                        region=region,
                        address=f'{address.street}, {address.number} — {address.neighborhood}' if address else 'Endereço fictício',
                        products=selected_products,
                        status=status,
                        admin=admin,
                        paid=past_or_today or day % 5 != 0,
                        seed=1000 + day * 10 + slot,
                    )

        # Populate the recurring-order item definitions after products exist.
        for index, cafe in enumerate(cafes):
            recurring = cafe.recurring_orders.first()
            if recurring:
                for product in [products[index % 4], products[(index + 1) % 4]]:
                    RecurringOrderItem.objects.update_or_create(
                        recurring_order=recurring,
                        product=product,
                        defaults={'quantity': 10 + index, 'note': 'Quantidade fictícia recorrente.'},
                    )

    def _events(self, year, users, products):
        statuses = ['new', 'review', 'sent', 'accepted', 'converted', 'declined']
        types = ['birthday', 'corporate', 'party', 'wedding', 'birthday', 'corporate']
        for index in range(6):
            quote = EventQuote.objects.create(
                customer=users[index],
                event_type=types[index],
                event_date=date(year, 9 if index < 4 else 10, 8 + index * 3),
                guest_count=30 + index * 25,
                address=f'Espaço fictício {index + 1} — Rio de Janeiro',
                notes='Orçamento fictício para demonstrar o pipeline de eventos.',
                status=statuses[index],
                estimated_total=Decimal('450.00') + Decimal(index * 210),
                final_total=(Decimal('520.00') + Decimal(index * 210)) if statuses[index] in {'accepted', 'converted'} else None,
            )
            EventQuoteItem.objects.create(
                quote=quote,
                product=products[index % len(products)],
                description='Seleção de doces para o evento',
                quantity=30 + index * 10,
                proposed_unit_price=ProductPrice.objects.filter(product=products[index % len(products)], table__kind='retail').first().unit_price,
            )

    def _messages(self, admin):
        rows = list(Conversation.objects.select_related('customer', 'order').order_by('-order__delivery_date')[:18])
        for index, conversation in enumerate(rows):
            if index % 3 == 0:
                Message.objects.create(
                    conversation=conversation,
                    sender=admin,
                    body='Oi! Está tudo confirmado por aqui. Quando sair para entrega, atualizamos o pedido.',
                    read_at=timezone.now() if index % 2 else None,
                )
            elif index % 3 == 1:
                Message.objects.create(
                    conversation=conversation,
                    sender=conversation.customer,
                    body='Perfeito, obrigada! Se possível, me avise quando estiver a caminho.',
                    read_at=None,
                )

    def _refresh_customer_metrics(self):
        for profile in CustomerProfile.objects.filter(user__username__startswith=DEMO_PREFIX).select_related('user'):
            completed = profile.user.orders.filter(status='completed')
            profile.orders_count = completed.count()
            profile.lifetime_value = sum((order.total for order in completed), Decimal('0.00'))
            profile.save(update_fields=['orders_count', 'lifetime_value', 'updated_at'])
