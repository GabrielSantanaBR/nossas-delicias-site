from django.test import TestCase
from django.urls import reverse


class PublicVisualSmokeTests(TestCase):
    def test_home_renders_public_v17_storefront(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Nossas Delícias', html)
        self.assertIn('brand-wordmark', html)
        self.assertIn('v15-cinematic.css', html)
        self.assertIn('public-v17.css', html)
        self.assertIn('public-v17.js', html)
        self.assertIn('hero-photo-shell', html)
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
