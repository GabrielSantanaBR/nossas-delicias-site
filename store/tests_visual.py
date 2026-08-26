from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


class PublicVisualSmokeTests(TestCase):
    def test_home_renders_public_v17_storefront(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Nossas Delícias', html)
        self.assertIn('brand-logo-frame', html)
        self.assertIn('brand/nossas-delicias-wordmark.png', html)
        self.assertIn('brand/nossas-delicias-seal.png', html)
        self.assertIn('rel="manifest"', html)
        self.assertIn('v15-cinematic.css', html)
        self.assertIn('public-v17.css', html)
        self.assertIn('public-v17.js', html)
        self.assertIn('brand-v19.css', html)
        self.assertIn('brand-v19.js', html)
        self.assertIn('hero-photo-shell', html)
        self.assertIn('hero-brand-seal', html)
        self.assertIn('portfolio-shell', html)
        self.assertIn('Nosso trabalho', html)
        self.assertIn('images/showcase/confeitaria-hero', html)
        self.assertIn('/monte-seu-bolo/', html)

    def test_anonymous_storefront_does_not_expose_private_management_navigation(self):
        response = self.client.get(reverse('home'))
        html = response.content.decode('utf-8')
        self.assertNotIn('href="/gestao/"', html)
        self.assertNotIn('href="/financeiro/"', html)
        self.assertNotIn('href="/nd-admin/"', html)
        self.assertNotIn('Central de Gestão', html)

    def test_public_navigation_never_exposes_team_tools_even_to_staff(self):
        staff = User.objects.create_user('visual-staff', password='VeryStrongPassword-123!', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get(reverse('home')).content.decode('utf-8')
        self.assertNotIn('href="/gestao/"', html)
        self.assertNotIn('href="/financeiro/"', html)
        self.assertNotIn('href="/nd-admin/"', html)
        self.assertIn('Pedidos e mensagens', html)

    def test_customer_cannot_open_private_financial_or_management_system(self):
        customer = User.objects.create_user('visual-customer', password='VeryStrongPassword-456!')
        self.client.force_login(customer)
        for route_name in ('management_center', 'finance_dashboard'):
            with self.subTest(route=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 403)

    def test_private_interfaces_are_noindex_and_admin_exposes_working_theme_toggle(self):
        staff = User.objects.create_user('theme-staff', password='VeryStrongPassword-789!', is_staff=True)
        device = TOTPDevice.objects.create(user=staff, name='visual-tests', confirmed=True)
        self.client.force_login(staff)
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        management = self.client.get(reverse('management_center'))
        finance = self.client.get(reverse('finance_dashboard'))
        admin = self.client.get('/nd-admin/')
        self.assertContains(management, 'noindex,nofollow,noarchive')
        self.assertContains(finance, 'noindex,nofollow,noarchive')
        self.assertContains(admin, 'theme-toggle')
        self.assertContains(admin, 'admin-nd.css')
        self.assertNotContains(admin, 'Importações de planilha')

    def test_private_management_routes_are_not_available_anonymously(self):
        for route_name in ('management_center', 'finance_dashboard'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)

    def test_core_public_routes_do_not_crash(self):
        for route_name in ('catalog', 'cake_studio', 'cafe_portal', 'event_portal'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_public_partnership_pages_explain_the_offer_before_login(self):
        cafe = self.client.get(reverse('cafe_portal'))
        events = self.client.get(reverse('event_portal'))
        self.assertContains(cafe, 'Quer levar Nossas Delícias para sua cafeteria?')
        self.assertContains(events, 'Eventos e encomendas especiais')
