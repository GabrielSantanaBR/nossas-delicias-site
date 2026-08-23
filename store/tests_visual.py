from django.test import TestCase
from django.urls import reverse


class PublicVisualSmokeTests(TestCase):
    def test_home_renders_v15_brand_and_motion_assets(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Nossas Delícias', html)
        self.assertIn('brand-wordmark', html)
        self.assertIn('v15-cinematic.css', html)
        self.assertIn('v15-cinematic.js', html)
        self.assertIn('hero-photo-shell', html)
        self.assertIn('data-story', html)

    def test_core_public_routes_do_not_crash(self):
        for route_name in ('catalog', 'cafe_portal', 'event_portal'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertIn(response.status_code, (200, 302))
