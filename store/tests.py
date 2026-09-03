import json
from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from .forms import EventQuoteForm
from .models import (
    CafeAccount,
    CakeDesign,
    CakeOption,
    Category,
    CustomerAddress,
    CustomerProfile,
    DeliveryRegion,
    DeliveryRoute,
    Order,
    Payment,
    PriceTable,
    Product,
    ProductPrice,
    EventQuote,
    EventQuoteItem,
    EventQuoteMessage,
    Favorite,
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
        self.assertNotIn("script-src 'self' 'unsafe-inline'", response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Cross-Origin-Resource-Policy'], 'same-origin')

    def test_authenticated_pages_are_not_stored_in_shared_browser_caches(self):
        self.client.login(username='cliente', password='StrongPassword-123!')
        response = self.client.get('/minha-conta/')
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store, max-age=0')

    def test_secure_admin_login_template_renders(self):
        response = self.client.get('/nd-admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Central Administrativa')
        self.assertContains(response, 'admin-nd')

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

    def test_customer_can_manage_profile_address_and_favorites(self):
        self.client.login(username='cliente', password='StrongPassword-123!')
        response = self.client.post('/minha-conta/perfil/', {
            'first_name': 'Gabriel', 'last_name': 'Santana', 'email': 'gabriel@example.com',
            'phone': '(21) 99999-0000', 'marketing_opt_in': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.user.customer_profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Gabriel')
        self.assertTrue(self.user.customer_profile.marketing_opt_in)

        response = self.client.post('/minha-conta/enderecos/salvar/', {
            'label': 'Casa', 'zip_code': '21660000', 'street': 'Rua do Teste',
            'number': '10', 'neighborhood': 'Guadalupe', 'city': 'Rio de Janeiro', 'default': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomerAddress.objects.filter(user=self.user, zip_code='21660-000', default=True).exists())

        response = self.client.post(f'/favoritos/{self.product.pk}/alternar/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['favorite'])
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_event_conversation_is_private_and_contextual(self):
        quote = EventQuote.objects.create(
            customer=self.user, event_type='birthday', event_date=timezone.localdate() + timedelta(days=30), guest_count=40,
        )
        other = User.objects.create_user('intruso', 'intruso@example.com', 'StrongPassword-456!')
        self.client.login(username='cliente', password='StrongPassword-123!')
        response = self.client.post(f'/eventos/orcamentos/{quote.public_id}/mensagem/', {'body': 'Prefiro chocolate meio amargo.'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EventQuoteMessage.objects.filter(quote=quote, sender=self.user).exists())
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/eventos/orcamentos/{quote.public_id}/').status_code, 404)

    def test_customer_accepts_only_a_complete_sent_event_proposal(self):
        quote = EventQuote.objects.create(
            customer=self.user, event_type='birthday', event_date=timezone.localdate() + timedelta(days=30),
            guest_count=40, status='sent',
        )
        EventQuoteItem.objects.create(
            quote=quote, product=self.product, quantity=10, proposed_unit_price=Decimal('8.00'),
        )
        self.client.login(username='cliente', password='StrongPassword-123!')
        response = self.client.post(f'/eventos/orcamentos/{quote.public_id}/aceitar/')
        self.assertEqual(response.status_code, 302)
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'accepted')
        self.assertEqual(quote.final_total, Decimal('80.00'))
        self.assertTrue(quote.status_history.filter(status='accepted', changed_by=self.user).exists())


class CakeStudioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('boleira', 'bolo@example.com', 'StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user)
        self.dough = CakeOption.objects.filter(kind='dough', active=True).first()
        self.filling = CakeOption.objects.filter(kind='filling', active=True).first()
        self.frosting = CakeOption.objects.filter(kind='frosting', active=True).first()

    def payload(self, **overrides):
        data = {
            'dough': self.dough.pk,
            'primary_filling': self.filling.pk,
            'secondary_filling': '',
            'complement': '',
            'frosting': self.frosting.pk,
            'decoration_style': 'floral',
            'guest_count': 35,
            'occasion': 'Aniversário de 30 anos',
            'event_date': timezone.localdate() + timedelta(days=20),
            'address': 'Rua das Flores, 120 · Rio de Janeiro',
            'decoration_notes': 'Flores delicadas em tons rosados.',
            'notes': 'Entrega no período da manhã.',
        }
        data.update(overrides)
        return data

    def test_public_studio_renders_seeded_menu(self):
        response = self.client.get('/monte-seu-bolo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monte camada por camada')
        self.assertContains(response, 'Amanteigada de baunilha')
        self.assertEqual(CakeOption.objects.filter(kind='dough').count(), 8)
        self.assertEqual(CakeOption.objects.filter(kind='filling').count(), 9)
        self.assertEqual(CakeOption.objects.filter(kind='complement').count(), 5)
        self.assertEqual(CakeOption.objects.filter(kind='frosting').count(), 4)

    def test_menu_products_and_prices_are_available_in_catalog(self):
        response = self.client.get('/cardapio/')
        self.assertContains(response, 'Brigadeiros gourmet 20 g · caixa 50')
        self.assertContains(response, 'Brownie 6×6 recheado · caixa 12')
        self.assertContains(response, 'Banoffee 24 cm')
        banoffee = Product.objects.get(slug='banoffee-24cm')
        self.assertEqual(banoffee.prices.get(table__kind='retail').unit_price, Decimal('150.00'))

    def test_authenticated_customer_creates_cake_quote(self):
        self.client.login(username='boleira', password='StrongPassword-123!')
        response = self.client.post('/monte-seu-bolo/', self.payload())
        quote = EventQuote.objects.get(customer=self.user)
        design = CakeDesign.objects.get(quote=quote)
        self.assertRedirects(response, f'/eventos/orcamentos/{quote.public_id}/')
        self.assertEqual(design.dough, self.dough)
        self.assertEqual(design.primary_filling, self.filling)
        self.assertEqual(design.selection_snapshot['decoration_style'], 'Floral delicado')
        self.assertTrue(quote.items.filter(description__contains=self.dough.name).exists())
        self.assertTrue(quote.status_history.filter(note__contains='estúdio de bolos').exists())
        detail = self.client.get(f'/eventos/orcamentos/{quote.public_id}/')
        self.assertContains(detail, 'Sua receita')
        self.assertContains(detail, self.dough.name)

    def test_wrong_kind_and_short_lead_time_are_rejected(self):
        self.client.login(username='boleira', password='StrongPassword-123!')
        response = self.client.post('/monte-seu-bolo/', self.payload(
            dough=self.filling.pk,
            event_date=timezone.localdate() + timedelta(days=2),
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faça uma escolha válida')
        self.assertContains(response, 'pelo menos 7 dias de antecedência')
        self.assertFalse(EventQuote.objects.filter(customer=self.user).exists())

    def test_anonymous_customer_is_sent_to_login_before_creating_quote(self):
        response = self.client.post('/monte-seu-bolo/', self.payload())
        self.assertRedirects(response, '/login/?next=/monte-seu-bolo/', fetch_redirect_response=False)
        self.assertFalse(CakeDesign.objects.exists())


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

    @patch('store.views.validate_webhook', return_value=False)
    def test_webhook_rejects_an_invalid_signature(self, mocked_validate):
        response = self.client.post(
            '/pagamentos/mercado-pago/webhook/?data.id=123',
            data=json.dumps({'data': {'id': '123'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

    @patch('store.views.fetch_payment')
    @patch('store.views.validate_webhook', return_value=True)
    def test_approved_webhook_rejects_amount_mismatch(self, mocked_validate, mocked_fetch):
        mocked_fetch.return_value = {
            'id': 123,
            'external_reference': str(self.order.public_id),
            'status': 'approved',
            'transaction_amount': '91.99',
            'currency_id': 'BRL',
            'payment_type_id': 'credit_card',
        }
        response = self.client.post(
            '/pagamentos/mercado-pago/webhook/?data.id=123',
            data=json.dumps({'data': {'id': '123'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        payment = Payment.objects.get(order=self.order, provider_id='123')
        self.assertEqual(self.order.status, 'pending_payment')
        self.assertEqual(payment.status, 'rejected')
        self.assertFalse(payment.raw_reference['amount_matches'])

    @patch('store.views.fetch_payment')
    @patch('store.views.validate_webhook', return_value=True)
    def test_matching_approved_webhook_marks_order_as_paid(self, mocked_validate, mocked_fetch):
        mocked_fetch.return_value = {
            'id': 456,
            'external_reference': str(self.order.public_id),
            'status': 'approved',
            'transaction_amount': '92.00',
            'currency_id': 'BRL',
            'payment_type_id': 'pix',
        }
        response = self.client.post(
            '/pagamentos/mercado-pago/webhook/?data.id=456',
            data=json.dumps({'data': {'id': '456'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        payment = Payment.objects.get(order=self.order, provider_id='456')
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(payment.status, 'approved')
        self.assertTrue(payment.raw_reference['amount_matches'])
        self.assertTrue(payment.raw_reference['currency_matches'])
