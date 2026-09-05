from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import CustomerProfile, DataSubjectRequest, Order


@override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID='G-TEST12345')
class PrivacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('privacidade', 'privacidade@example.com', 'StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user, phone='21999990000')

    def test_analytics_requires_an_explicit_cookie_choice(self):
        first = self.client.get('/')
        self.assertContains(first, 'data-cookie-banner')
        self.assertContains(first, 'data-analytics-id="G-TEST12345"')
        self.assertContains(first, 'data-analytics-consent="unknown"')
        self.assertIn('https://www.googletagmanager.com', first.headers['Content-Security-Policy'])
        self.assertIn('Cookie', first.headers['Vary'])

        response = self.client.post('/privacidade/cookies/', {'analytics': '0'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('nd_cookie_preferences', response.cookies)
        denied = self.client.get('/')
        self.assertContains(denied, 'data-analytics-consent="denied"')

    def test_privacy_request_is_rate_limited_workflow_not_immediate_deletion(self):
        response = self.client.post('/privacidade/solicitacoes/', {
            'email': 'titular@example.com',
            'request_type': 'deletion',
            'details': 'Quero entender quais dados podem ser eliminados.',
            'confirmation': 'on',
        })
        self.assertEqual(response.status_code, 302)
        item = DataSubjectRequest.objects.get(email='titular@example.com')
        self.assertEqual(item.status, 'new')
        self.assertEqual(item.request_type, 'deletion')

    def test_logged_in_customer_can_export_only_own_data(self):
        Order.objects.create(customer=self.user, total='18.50', delivery_address='Rua de teste, 10')
        self.client.login(username='privacidade', password='StrongPassword-123!')
        response = self.client.post('/privacidade/exportar-meus-dados/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="nossas-delicias-meus-dados.json"')
        self.assertContains(response, 'privacidade@example.com')
        self.assertContains(response, 'Rua de teste, 10')
