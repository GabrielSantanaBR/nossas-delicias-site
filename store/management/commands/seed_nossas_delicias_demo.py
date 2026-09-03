import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from store.financial_models import BusinessExpense, CafeDeliveryNote, ProductCostProfile
from store.financial_services import ensure_cafe_note, lock_cafe_note, refresh_order_financials
from store.management_models import FinancialSettings, FixedCost, Ingredient, InventoryMovement, Recipe
from store.models import (
    CafeAccount, Category, Conversation, CustomerAddress, CustomerProfile,
    DeliveryRegion, DeliveryRoute, EventQuote, EventQuoteItem, Message, Order,
    OrderItem, OrderStatusHistory, Payment, PriceTable, Product, ProductPrice,
    RecurringOrder, RecurringOrderItem,
)

DEMO_PREFIX = 'demo_'
DEMO_MARKER = '[DEMO]'


def aware(day, hour=10, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = 'Preenche a plataforma com dados fictícios completos de demonstração.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=timezone.localdate().year)
        parser.add_argument('--demo-password', default='')
        parser.add_argument('--admin-password', default='')

    @transaction.atomic
    def handle(self, *args, **options):
        year = options['year']
        today = timezone.localdate()
        self._cleanup()
        admin = self._user('demo_admin', 'Operação', 'Nossas Delícias', 'demo-admin@example.invalid', options['admin_password'], True, True)
        retail_table, cafe_table = self._tables()
        products = self._products(retail_table, cafe_table)
        self._finance_and_stock(admin, year)
        regions = self._routes()
        customers = self._customers(options['demo_password'])
        cafes = self._cafes(options['demo_password'], cafe_table, regions)
        self._pending_cafe(options['demo_password'])
        self._august(year, today, admin, customers, cafes, products, regions)
        self._events(year, customers, products)
        self._messages(admin)
        self._metrics()

        self.stdout.write(self.style.SUCCESS(f'Demo agosto/{year} criada.'))
        self.stdout.write('Painel operacional: /gestao/')
        self.stdout.write('Admin avançado: /nd-admin/')
        self.stdout.write('Regras: clientes com 7 dias de antecedência e limite de 5/dia; cafeterias terça/quinta/sexta no Centro/Zona Sul.')

    def _cleanup(self):
        orders = Order.objects.filter(customer__username__startswith=DEMO_PREFIX)
        Payment.objects.filter(order__in=orders).delete()
        CafeDeliveryNote.objects.filter(order__in=orders).delete()
        OrderStatusHistory.objects.filter(order__in=orders).delete()
        orders.delete()
        EventQuote.objects.filter(customer__username__startswith=DEMO_PREFIX).delete()
        BusinessExpense.objects.filter(description__startswith=DEMO_MARKER).delete()
        InventoryMovement.objects.filter(reference__startswith=DEMO_MARKER).delete()

    def _user(self, username, first, last, email, password='', staff=False, superuser=False):
        user, created = User.objects.get_or_create(username=username)
        user.first_name, user.last_name, user.email = first, last, email
        user.is_active, user.is_staff, user.is_superuser = True, staff, superuser
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()
        user.save()
        return user

    def _tables(self):
        retail, _ = PriceTable.objects.update_or_create(name='Clientes — Nossas Delícias', defaults={'kind': 'retail', 'active': True})
        cafe, _ = PriceTable.objects.update_or_create(name='Cafeterias parceiras — B2B', defaults={'kind': 'cafe', 'active': True})
        return retail, cafe

    def _products(self, retail_table, cafe_table):
        cats = {}
        for i, (name, slug) in enumerate([('Brownies', 'brownies'), ('Bolos & Fatias', 'bolos-fatias'), ('Caixas & Presentes', 'caixas-presentes')]):
            cats[slug], _ = Category.objects.update_or_create(slug=slug, defaults={'name': name, 'active': True, 'sort_order': i})
        rows = [
            ('ND-BR-001', 'brownies', 'Brownie Tradicional', 'Chocolate intenso, centro úmido e casquinha delicada.', '10.90', '7.20', '3.20'),
            ('ND-BR-002', 'brownies', 'Brownie Brigadeiro', 'Brownie com cobertura cremosa de brigadeiro.', '12.50', '8.10', '3.70'),
            ('ND-BR-003', 'brownies', 'Brownie Doce de Leite', 'Chocolate com doce de leite em equilíbrio.', '12.50', '8.10', '3.65'),
            ('ND-BR-004', 'brownies', 'Brownie Ninho', 'Brownie com cobertura suave de leite em pó.', '13.50', '8.70', '4.10'),
            ('ND-FT-001', 'bolos-fatias', 'Fatia Bolo de Chocolate', 'Fatia alta com cobertura de chocolate.', '14.90', '9.50', '4.40'),
            ('ND-FT-002', 'bolos-fatias', 'Fatia Bolo de Cenoura', 'Massa de cenoura com cobertura de chocolate.', '13.90', '8.90', '4.00'),
            ('ND-CX-006', 'caixas-presentes', 'Caixa com 6 Brownies', 'Caixa para compartilhar ou presentear.', '62.00', '42.00', '19.00'),
            ('ND-CX-012', 'caixas-presentes', 'Caixa Presente com 12', 'Doze unidades em caixa presenteável.', '118.00', '78.00', '38.00'),
        ]
        products = []
        for i, (sku, cat, name, desc, retail, cafe, cost) in enumerate(rows):
            slug = sku.lower()
            product, _ = Product.objects.update_or_create(
                slug=slug,
                defaults={
                    'category': cats[cat], 'name': name, 'description': desc,
                    # Showcase images are selected locally by product type until
                    # the team uploads the final photography in management.
                    'image': '', 'active': True, 'featured': i < 6,
                    'sell_retail': True, 'sell_cafe': True, 'sell_event': False,
                    'min_quantity': 1, 'lead_time_days': 7, 'stock_limit': 500, 'sort_order': i,
                },
            )
            ProductPrice.objects.update_or_create(product=product, table=retail_table, min_quantity=1, defaults={'unit_price': Decimal(retail)})
            ProductPrice.objects.update_or_create(product=product, table=cafe_table, min_quantity=1, defaults={'unit_price': Decimal(cafe)})
            ProductCostProfile.objects.update_or_create(
                product=product,
                defaults={'sku': sku, 'sale_unit': 'box' if 'CX' in sku else 'unit', 'yield_quantity': 1, 'production_cost': Decimal(cost), 'source_reference': 'Demo operacional', 'active': True},
            )
            Recipe.objects.update_or_create(
                code=sku,
                defaults={'name': name, 'category': cats[cat].name, 'sale_unit': 'box' if 'CX' in sku else 'unit', 'yield_quantity': 1, 'imported_production_cost': Decimal(cost), 'product': product, 'active': True, 'source_reference': 'Demo operacional'},
            )
            products.append(product)
        return products

    def _finance_and_stock(self, admin, year):
        settings = FinancialSettings.current()
        settings.desired_margin_percent = Decimal('35')
        settings.payment_fee_percent = Decimal('4.5')
        settings.contingency_percent = Decimal('3')
        settings.save()
        for name, category, amount, due in [
            ('Estrutura de produção', 'rent', '700', 5), ('Água, luz, gás e internet', 'utilities', '260', 10),
            ('Sistemas e ferramentas', 'software', '120', 12), ('Reserva logística', 'logistics', '350', 15),
        ]:
            FixedCost.objects.update_or_create(name=f'{DEMO_MARKER} {name}', defaults={'category': category, 'monthly_amount': Decimal(amount), 'due_day': due, 'active': True, 'start_date': date(year, 1, 1)})
        for d, cat, text, amount, status in [
            (2, 'ingredient', 'Chocolate e cacau', '860', 'paid'), (5, 'packaging', 'Embalagens e caixas', '335', 'paid'),
            (9, 'logistics', 'Combustível e entregas', '475', 'paid'), (14, 'ingredient', 'Laticínios e secos', '610', 'paid'),
            (18, 'marketing', 'Conteúdo e divulgação', '190', 'paid'), (22, 'fees', 'Taxas e serviços', '128', 'paid'),
            (28, 'packaging', 'Reposição de caixas', '280', 'pending'),
        ]:
            BusinessExpense.objects.create(date=date(year, 8, d), category=cat, description=f'{DEMO_MARKER} {text}', supplier='Fornecedor fictício', amount=Decimal(amount), payment_status=status, payment_method='Pix' if status == 'paid' else '', created_by=admin)
        for i, (name, price, qty, unit, stock, minimum) in enumerate([
            ('Chocolate 100%', '42.90', '1000', 'g', '8000', '1500'), ('Farinha', '8.50', '1000', 'g', '9000', '1800'),
            ('Açúcar', '6.90', '1000', 'g', '7500', '1500'), ('Manteiga', '19.90', '500', 'g', '4200', '900'),
            ('Ovos', '18', '12', 'un', '180', '36'), ('Leite condensado', '7.90', '395', 'g', '5200', '900'),
            ('Embalagem brownie', '24', '100', 'un', '520', '100'), ('Caixa presente', '39', '20', 'un', '90', '20'),
        ], 1):
            ingredient, _ = Ingredient.objects.update_or_create(code=f'ING-DEM-{i:02d}', defaults={'name': name, 'category': 'Demo', 'package_price': Decimal(price), 'package_quantity': Decimal(qty), 'base_unit': unit, 'supplier': 'Fornecedor fictício', 'active': True, 'minimum_stock': Decimal(minimum), 'last_price_update': date(year, 8, 1)})
            InventoryMovement.objects.create(ingredient=ingredient, movement_type='purchase', quantity_delta=Decimal(stock), date=date(year, 8, 1), reference=f'{DEMO_MARKER} estoque inicial', created_by=admin)
            InventoryMovement.objects.create(ingredient=ingredient, movement_type='production', quantity_delta=Decimal(stock) * Decimal('0.42'), date=date(year, 8, 20), reference=f'{DEMO_MARKER} produção agosto', created_by=admin)

    def _routes(self):
        data = {
            'nilopolis': ('Nilópolis — Clientes', '9', '35', '265,266'),
            'west': ('Zona Oeste — Clientes', '14', '45', '217,218,227,230,235'),
            'center': ('Centro — Cafeterias', '0', '120', '200,201,202'),
            'south': ('Zona Sul — Cafeterias', '0', '150', '220,222,224,226'),
        }
        regions = {}
        for key, (name, fee, minimum, prefixes) in data.items():
            regions[key], _ = DeliveryRegion.objects.update_or_create(name=name, defaults={'active': True, 'delivery_fee': Decimal(fee), 'minimum_order': Decimal(minimum), 'zip_prefixes': prefixes})
        retail, _ = DeliveryRoute.objects.update_or_create(name='Clientes | Nilópolis + Zona Oeste', defaults={'active': True, 'weekdays': '0,1,2,3,4,5', 'default_capacity': 5, 'start_time': time(10), 'end_time': time(18)})
        retail.regions.set([regions['nilopolis'], regions['west']])
        cafe, _ = DeliveryRoute.objects.update_or_create(name='Cafeterias | Centro + Zona Sul', defaults={'active': True, 'weekdays': '1,3,4', 'default_capacity': 24, 'start_time': time(8), 'end_time': time(14)})
        cafe.regions.set([regions['center'], regions['south']])
        return regions

    def _customers(self, password):
        names = [('Marina','Alves'),('Lucas','Moura'),('Bianca','Silva'),('Rafael','Costa'),('Isabela','Rocha'),('Caio','Martins'),('Larissa','Souza'),('Pedro','Lima'),('Ana','Ferreira'),('Bruno','Carvalho'),('Julia','Ramos'),('Diego','Nunes'),('Camila','Duarte'),('Mateus','Pires')]
        result = []
        for i, (first, last) in enumerate(names, 1):
            username = f'demo_cliente_{i:02d}'
            user = self._user(username, first, last, f'{username}@example.invalid', password)
            CustomerProfile.objects.update_or_create(user=user, defaults={'customer_type': 'retail', 'phone': f'(21) 90000-{1000+i:04d}', 'notes': 'Conta fictícia.'})
            CustomerAddress.objects.update_or_create(user=user, label='Principal', defaults={'zip_code': '26510-100' if i % 2 else '22775-100', 'street': 'Rua Demonstração', 'number': str(100+i), 'city': 'Nilópolis' if i % 2 else 'Rio de Janeiro', 'default': True})
            result.append(user)
        return result

    def _cafes(self, password, cafe_table, regions):
        rows = [
            ('Café Aurora Centro', 'Centro', '20040-020', 'center', 'Helena Prado'),
            ('Botafogo Doce Café', 'Botafogo', '22250-040', 'south', 'Miguel Torres'),
            ('Café Jardim Flamengo', 'Flamengo', '22220-030', 'south', 'Clara Reis'),
            ('Copacabana Grão & Afeto', 'Copacabana', '22040-010', 'south', 'Theo Campos'),
            ('Ipanema Café Estúdio', 'Ipanema', '22410-020', 'south', 'Lia Azevedo'),
            ('Leblon Ponto Doce', 'Leblon', '22440-030', 'south', 'Davi Freitas'),
        ]
        result = []
        for i, (business, neighborhood, zip_code, region_key, contact) in enumerate(rows, 1):
            username = f'demo_cafe_{i:02d}'
            user = self._user(username, contact.split()[0], contact.split()[-1], f'{username}@example.invalid', password)
            CustomerProfile.objects.update_or_create(user=user, defaults={'customer_type': 'cafe', 'notes': 'Cafeteria fictícia aprovada.'})
            cafe, _ = CafeAccount.objects.update_or_create(user=user, defaults={'business_name': business, 'contact_name': contact, 'approved': True, 'active': True, 'minimum_order': Decimal('150'), 'price_table': cafe_table, 'internal_note': 'Conta B2B fictícia autorizada.'})
            CustomerAddress.objects.update_or_create(user=user, label='Cafeteria', defaults={'zip_code': zip_code, 'street': 'Avenida Comercial Demo', 'number': str(20+i), 'neighborhood': neighborhood, 'city': 'Rio de Janeiro', 'default': True})
            recurring, _ = RecurringOrder.objects.update_or_create(cafe=cafe, name='Reposição semanal', defaults={'weekday': [1,3,4][(i-1)%3], 'active': True, 'delivery_region': regions[region_key], 'delivery_address': f'Avenida Comercial Demo, {20+i} — {neighborhood}'})
            result.append(cafe)
        return result

    def _pending_cafe(self, password):
        user = self._user('demo_cafe_pendente', 'Conta', 'Pendente', 'demo_cafe_pendente@example.invalid', password)
        CustomerProfile.objects.update_or_create(user=user, defaults={'customer_type': 'cafe', 'notes': 'Solicitação B2B fictícia aguardando autorização.'})
        CafeAccount.objects.update_or_create(user=user, defaults={'business_name': 'Café Horizonte — aguardando análise', 'contact_name': 'Conta Pendente', 'approved': False, 'active': True, 'minimum_order': Decimal('150'), 'price_table': None, 'internal_note': 'Não liberar B2B antes da aprovação.'})

    def _make_order(self, user, order_type, delivery_date, region, products, admin, seed, completed):
        table_kind = 'cafe' if order_type == 'cafe' else 'retail'
        lines, subtotal = [], Decimal('0')
        for offset, product in enumerate(products):
            price = ProductPrice.objects.filter(product=product, table__kind=table_kind).order_by('min_quantity').first().unit_price
            qty = 8 + ((seed + offset) % 6) if order_type == 'cafe' else 1 + ((seed + offset) % 3)
            if 'Caixa' in product.name:
                qty = 2 if order_type == 'cafe' else 1
            lines.append((product, qty, price)); subtotal += price * qty
        status = 'completed' if completed else ['paid', 'production', 'ready'][seed % 3]
        order = Order.objects.create(customer=user, order_type=order_type, status=status, delivery_date=delivery_date, delivery_region=region, delivery_address='Endereço fictício de demonstração', delivery_fee=region.delivery_fee, subtotal=money(subtotal), total=money(subtotal + region.delivery_fee), internal_note=f'{DEMO_MARKER} agosto')
        created_day = delivery_date - timedelta(days=8)
        Order.objects.filter(pk=order.pk).update(created_at=aware(created_day, 11, seed % 50))
        order.refresh_from_db()
        for product, qty, price in lines:
            OrderItem.objects.create(order=order, product=product, quantity=qty, unit_price=price)
        OrderStatusHistory.objects.create(order=order, status=status, changed_by=admin, note='Fluxo fictício de demonstração.')
        Conversation.objects.get_or_create(order=order, defaults={'customer': user})
        Payment.objects.create(order=order, provider='demo', provider_id=f'demo-{order.public_id}', status='approved' if completed or seed % 4 else 'pending', amount=order.total, method='pix', paid_at=aware(created_day, 12) if completed or seed % 4 else None, raw_reference={'fictional': True})
        refresh_order_financials(order, allow_locked=True)
        if order_type == 'cafe' and completed:
            lock_cafe_note(ensure_cafe_note(order), user=admin, force=True)
        return order

    def _august(self, year, today, admin, customers, cafes, products, regions):
        retail_i = cafe_i = 0
        for day in range(1, calendar.monthrange(year, 8)[1] + 1):
            current = date(year, 8, day)
            if current.weekday() in {0,1,2,3,4,5}:
                for slot in range(2 + day % 2):
                    user = customers[retail_i % len(customers)]; retail_i += 1
                    region = regions['nilopolis'] if (day + slot) % 2 else regions['west']
                    chosen = [products[(day+slot) % 6], products[(day+slot+2) % 6]]
                    self._make_order(user, 'retail', current, region, chosen, admin, day*10+slot, current <= today)
            if current.weekday() in {1,3,4}:
                for slot in range(2):
                    cafe = cafes[cafe_i % len(cafes)]; cafe_i += 1
                    address = cafe.user.saved_addresses.filter(default=True).first()
                    region = regions['center'] if address and address.neighborhood == 'Centro' else regions['south']
                    chosen = [products[(day+slot) % 6], products[(day+slot+1) % 6], products[6]]
                    self._make_order(cafe.user, 'cafe', current, region, chosen, admin, 1000+day*10+slot, current <= today)
        for i, cafe in enumerate(cafes):
            recurring = cafe.recurring_orders.first()
            for product in [products[i % 4], products[(i+1) % 4]]:
                RecurringOrderItem.objects.update_or_create(recurring_order=recurring, product=product, defaults={'quantity': 10+i})

    def _events(self, year, customers, products):
        statuses = ['new','review','sent','accepted','converted','declined']
        for i in range(6):
            quote = EventQuote.objects.create(customer=customers[i], event_type=['birthday','corporate','party','wedding','birthday','corporate'][i], event_date=date(year, 9 if i < 4 else 10, 8+i*3), guest_count=30+i*25, address=f'Espaço fictício {i+1}', notes='Orçamento fictício.', status=statuses[i], estimated_total=Decimal('450')+i*Decimal('210'))
            EventQuoteItem.objects.create(quote=quote, product=products[i], description='Seleção de doces', quantity=30+i*10, proposed_unit_price=ProductPrice.objects.filter(product=products[i], table__kind='retail').first().unit_price)

    def _messages(self, admin):
        for i, conversation in enumerate(Conversation.objects.select_related('customer').order_by('-order__delivery_date')[:18]):
            sender = conversation.customer if i % 2 else admin
            Message.objects.create(conversation=conversation, sender=sender, body='Olá! Só confirmando os detalhes da entrega.' if sender == conversation.customer else 'Está tudo confirmado. Avisaremos quando sair para entrega.', read_at=None if sender == conversation.customer else timezone.now())

    def _metrics(self):
        for profile in CustomerProfile.objects.filter(user__username__startswith=DEMO_PREFIX).select_related('user'):
            completed = profile.user.orders.filter(status='completed')
            profile.orders_count = completed.count()
            profile.lifetime_value = sum((o.total for o in completed), Decimal('0'))
            profile.save(update_fields=['orders_count','lifetime_value','updated_at'])
