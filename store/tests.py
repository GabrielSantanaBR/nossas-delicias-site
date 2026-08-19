from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .models import Category,CustomerProfile,DeliveryRegion,PriceTable,Product,ProductPrice
from .services import price_for,region_for_zip

class CommerceServiceTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('cliente','cliente@example.com','StrongPassword-123!')
        CustomerProfile.objects.create(user=self.user)
        self.category=Category.objects.create(name='Brownies',slug='brownies')
        self.product=Product.objects.create(category=self.category,name='Brownie',slug='brownie',description='Teste',image='products/test.jpg')
        self.table=PriceTable.objects.create(name='Varejo',kind='retail')
        ProductPrice.objects.create(product=self.product,table=self.table,min_quantity=1,unit_price=Decimal('8.00'))
        ProductPrice.objects.create(product=self.product,table=self.table,min_quantity=10,unit_price=Decimal('6.50'))
        DeliveryRegion.objects.create(name='Guadalupe',delivery_fee=Decimal('5.00'),minimum_order=Decimal('20.00'),zip_prefixes='21660,21665')

    def test_quantity_tier_price(self):
        self.assertEqual(price_for(self.user,self.product,1,'retail'),Decimal('8.00'))
        self.assertEqual(price_for(self.user,self.product,10,'retail'),Decimal('6.50'))

    def test_zip_region(self):
        self.assertEqual(region_for_zip('21660-000').name,'Guadalupe')
        self.assertIsNone(region_for_zip('20000-000'))

    def test_customer_cannot_open_another_users_order(self):
        other=User.objects.create_user('outro','outro@example.com','StrongPassword-123!')
        from .models import Order
        order=Order.objects.create(customer=other,total=Decimal('10.00'))
        self.client.login(username='cliente',password='StrongPassword-123!')
        response=self.client.get(f'/pedidos/{order.public_id}/')
        self.assertEqual(response.status_code,404)
