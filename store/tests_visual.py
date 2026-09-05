from pathlib import Path
from decimal import Decimal

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
from PIL import Image

from .models import BrandProfile, CafeLocation, Category, Product
from .templatetags.store_tags import category_story, product_visual


class PublicVisualSmokeTests(TestCase):
    def test_home_renders_canonical_storefront_assets(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Nossas Delícias', html)
        self.assertIn('brand-lockup-wordmark', html)
        self.assertIn('brand/nossas-delicias-wordmark.', html)
        self.assertIn('brand/nossas-delicias-seal.', html)
        self.assertIn('rel="manifest"', html)
        self.assertIn('site.', html)
        self.assertIn('app.', html)
        self.assertNotIn('app.css', html)
        self.assertNotIn('v15-cinematic.css', html)
        self.assertNotIn('public-v17.css', html)
        self.assertNotIn('brand-v19.css', html)
        self.assertNotIn('public-v17.js', html)
        self.assertNotIn('brand-v19.js', html)
        self.assertIn('storefront-hero', html)
        self.assertIn('storefront-hero-media', html)
        self.assertIn('portfolio-shell', html)
        self.assertIn('home-guide', html)
        self.assertIn('Tem uma delícia para o que você quer viver hoje.', html)
        self.assertIn('brand-story', html)
        self.assertIn('Quem faz', html)
        self.assertIn('Desde', html)
        self.assertIn('Nosso trabalho', html)
        self.assertIn('images/showcase/confeitaria-hero', html)
        self.assertIn('/monte-seu-bolo/', html)
        self.assertIn('og:title', html)
        self.assertIn('canonical', html)

    def test_home_components_have_canonical_layout_rules(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'site.css').read_text(encoding='utf-8')
        for selector in (
            '.storefront-hero', '.storefront-hero-media', '.portfolio-shell',
            '.portfolio-grid', '.portfolio-media', '.public-process-grid',
            '.home-guide', '.occasion-list', '.catalog-hero', '.catalog-paths',
            '.category-showcase', '.brand-story', '.brand-facts', '.cafe-directory-grid',
            '.cafe-directory-card', '.auth-page', '.auth-panel',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)
        self.assertIn('.footer-symbol-lockup > img', css)
        self.assertIn('width: 64px !important', css)

    def test_catalogue_showcase_assets_exist_and_demo_media_never_breaks(self):
        showcase = Path(settings.BASE_DIR) / 'static' / 'images' / 'showcase' / 'catalog'
        for filename in (
            'brownie-classic.webp', 'brownie-box.webp', 'brownie-stack.webp',
            'cake-slice.webp', 'brigadeiro.webp', 'event-sweets.webp', 'gift-box.webp',
        ):
            with self.subTest(filename=filename):
                asset = showcase / filename
                self.assertTrue(asset.is_file())
                with Image.open(asset) as image:
                    self.assertEqual(image.format, 'WEBP')
                    self.assertGreaterEqual(image.width, 1000)
                    self.assertGreaterEqual(image.height, 700)
                    image.verify()

        category = Category.objects.create(name='Brownies visuais', slug='brownies-visuais')
        product = Product.objects.create(
            category=category,
            name='Brownie visual',
            slug='brownie-visual',
            description='Imagem de demonstração local.',
            image='products/demo/broken.jpg',
        )
        visual = product_visual(product)
        self.assertIn('images/showcase/catalog/brownie-classic', visual)
        self.assertNotIn('/media/products/demo/', visual)

        app_js = (Path(settings.BASE_DIR) / 'static' / 'app.js').read_text(encoding='utf-8')
        self.assertIn("img[data-fallback-src]", app_js)
        self.assertIn('revealReachedNodes', app_js)

    def test_catalog_is_a_guided_storefront_not_only_a_product_grid(self):
        category = Category.objects.create(name='Brownies', slug='brownies')
        Product.objects.create(
            category=category,
            name='Brownie da vitrine',
            slug='brownie-da-vitrine',
            description='Produto de teste para a vitrine editorial.',
            image='',
        )
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        for expected in (
            'catalog-hero', 'Tem doce para a vontade de agora',
            'Escolher agora', 'Montar um bolo', 'Planejar um evento',
            'catalog-closing',
            'category--cocoa', 'brownie-classic', 'Brownie da vitrine',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)

        story = category_story(Category(name='Brownies', slug='brownies'))
        self.assertEqual(story['tone'], 'cocoa')
        self.assertIn('brownie-classic.webp', story['image'])

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
        self.assertContains(admin, 'admin-nd')
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
        self.assertContains(cafe, 'Cafeterias que recebem Nossas Delícias.')
        self.assertContains(cafe, 'class="cafe-directory-card"', count=6)
        self.assertContains(cafe, 'Logo da cafeteria', count=6)
        self.assertContains(events, 'Eventos e encomendas especiais')

    def test_public_authentication_never_shows_raw_django_username_help(self):
        login = self.client.get(reverse('login'))
        register = self.client.get(reverse('register'))
        self.assertContains(login, 'E-mail ou usuário')
        self.assertContains(login, 'data-password-toggle')
        self.assertContains(register, 'Ex.: GabrielBezerra!!')
        self.assertContains(register, 'Pode usar letras, números e . @ + - _ !')
        self.assertNotContains(register, 'Obrigatório. 150 caracteres ou menos.')

    def test_cake_builder_exposes_progressive_validation_and_login_preservation(self):
        response = self.client.get(reverse('cake_studio'))
        self.assertContains(response, 'data-cake-validation')
        self.assertContains(response, 'sign_in_to_send')
        self.assertContains(response, 'imagem de referência deverá ser escolhida novamente')
        builder_js = (Path(settings.BASE_DIR) / 'static' / 'cake-builder.js').read_text(encoding='utf-8')
        self.assertIn('firstInvalidUntil', builder_js)
        self.assertIn('nd-cake-builder-selections-v1', builder_js)
        self.assertIn('defaultOptionalChoice', builder_js)
        self.assertIn('guestCount.defaultValue', builder_js)

    def test_public_brand_and_cafe_slots_render_real_content_when_it_is_added(self):
        BrandProfile.objects.create(
            owner_names='Nome dos donos',
            operating_since=2021,
            location='Cidade da marca',
        )
        CafeLocation.objects.create(
            slot=1,
            name='Cafeteria da parceira',
            location='Bairro da parceira',
            rating=Decimal('4.8'),
            delivery_note='Entrega de quarta a sábado.',
        )

        home = self.client.get(reverse('home'))
        cafe = self.client.get(reverse('cafe_portal'))

        self.assertContains(home, 'Nome dos donos')
        self.assertContains(home, '2021')
        self.assertContains(home, 'Cidade da marca')
        self.assertContains(cafe, 'Cafeteria da parceira')
        self.assertContains(cafe, 'Bairro da parceira')
        self.assertContains(cafe, '4,8/5')
        self.assertContains(cafe, 'Entrega de quarta a sábado.')

    def test_public_discovery_endpoints_exclude_private_routes(self):
        robots = self.client.get(reverse('robots_txt'))
        sitemap = self.client.get(reverse('sitemap_xml'))
        llms = self.client.get(reverse('llms_txt'))
        full = self.client.get(reverse('llms_full_txt'))
        self.assertEqual(robots.status_code, 200)
        self.assertEqual(sitemap.status_code, 200)
        self.assertEqual(llms.status_code, 200)
        self.assertEqual(full.status_code, 200)
        self.assertIn('/sitemap.xml', robots.content.decode())
        sitemap_body = sitemap.content.decode()
        self.assertIn('/cardapio/', sitemap_body)
        self.assertIn('/monte-seu-bolo/', sitemap_body)
        self.assertNotIn('/gestao/', sitemap_body)
        self.assertNotIn('/financeiro/', sitemap_body)
        self.assertNotIn('/nd-admin/', sitemap_body)
        llms_body = llms.content.decode()
        self.assertIn('/cardapio/', llms_body)
        self.assertNotIn('/gestao/', llms_body)
        self.assertNotIn('/financeiro/', llms_body)
