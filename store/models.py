import uuid
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models

class TimeStamped(models.Model):
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: abstract=True

class CustomerProfile(TimeStamped):
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Eventos')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='customer_profile')
    customer_type=models.CharField(max_length=12,choices=TYPES,default='retail')
    phone=models.CharField(max_length=24,blank=True); birth_date=models.DateField(null=True,blank=True)
    marketing_opt_in=models.BooleanField(default=False); orders_count=models.PositiveIntegerField(default=0); lifetime_value=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    notes=models.TextField(blank=True,help_text='Somente equipe interna.')
    def __str__(self): return self.user.get_full_name() or self.user.username

class Category(TimeStamped):
    name=models.CharField(max_length=100); slug=models.SlugField(unique=True); description=models.TextField(blank=True)
    image=models.ImageField(upload_to='categories/',blank=True,null=True); active=models.BooleanField(default=True); sort_order=models.PositiveIntegerField(default=0)
    class Meta: ordering=['sort_order','name']; verbose_name_plural='Categorias'
    def __str__(self): return self.name

class Product(TimeStamped):
    category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name='products')
    name=models.CharField(max_length=140); slug=models.SlugField(unique=True); description=models.TextField()
    image=models.ImageField(upload_to='products/'); active=models.BooleanField(default=True); featured=models.BooleanField(default=False)
    min_quantity=models.PositiveIntegerField(default=1); lead_time_days=models.PositiveIntegerField(default=1); stock_limit=models.PositiveIntegerField(null=True,blank=True)
    sort_order=models.PositiveIntegerField(default=0)
    class Meta: ordering=['category__sort_order','sort_order','name']
    def __str__(self): return self.name

class ProductImage(TimeStamped):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='gallery'); image=models.ImageField(upload_to='products/gallery/'); alt_text=models.CharField(max_length=180,blank=True); sort_order=models.PositiveIntegerField(default=0)

class PriceTable(TimeStamped):
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Eventos'),('custom','Personalizada')]
    name=models.CharField(max_length=100); kind=models.CharField(max_length=12,choices=TYPES); active=models.BooleanField(default=True)
    assigned_users=models.ManyToManyField(User,blank=True,related_name='price_tables')
    def __str__(self): return self.name

class ProductPrice(TimeStamped):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='prices'); table=models.ForeignKey(PriceTable,on_delete=models.CASCADE,related_name='prices')
    min_quantity=models.PositiveIntegerField(default=1); unit_price=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(Decimal('0.01'))])
    class Meta: ordering=['product','table','min_quantity']; unique_together=('product','table','min_quantity')

class DeliveryRegion(TimeStamped):
    name=models.CharField(max_length=120); active=models.BooleanField(default=True); delivery_fee=models.DecimalField(max_digits=8,decimal_places=2,default=0)
    minimum_order=models.DecimalField(max_digits=10,decimal_places=2,default=0); zip_prefixes=models.TextField(blank=True,help_text='Prefixos de CEP separados por vírgula.')
    def __str__(self): return self.name
    def matches_zip(self, value):
        digits=''.join(filter(str.isdigit,value or ''))
        return any(digits.startswith(p.strip()) for p in self.zip_prefixes.split(',') if p.strip())

class DeliveryRoute(TimeStamped):
    name=models.CharField(max_length=120); regions=models.ManyToManyField(DeliveryRegion,related_name='routes'); active=models.BooleanField(default=True)
    weekdays=models.CharField(max_length=20,help_text='0=segunda ... 6=domingo. Ex: 1,3,5'); default_capacity=models.PositiveIntegerField(default=30)
    start_time=models.TimeField(); end_time=models.TimeField()
    def weekday_set(self): return {int(v) for v in self.weekdays.split(',') if v.strip().isdigit()}
    def __str__(self): return self.name

class AvailabilityDay(TimeStamped):
    date=models.DateField(unique=True); enabled=models.BooleanField(default=True); capacity=models.PositiveIntegerField(default=30); note=models.CharField(max_length=200,blank=True)
    def __str__(self): return str(self.date)

class Order(TimeStamped):
    STATUSES=[('draft','Rascunho'),('pending_payment','Aguardando pagamento'),('paid','Pago'),('production','Em produção'),('ready','Pronto'),('delivery','Saiu para entrega'),('completed','Concluído'),('cancelled','Cancelado')]
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Evento')]
    public_id=models.UUIDField(default=uuid.uuid4,unique=True,editable=False); customer=models.ForeignKey(User,on_delete=models.PROTECT,related_name='orders')
    order_type=models.CharField(max_length=12,choices=TYPES,default='retail'); status=models.CharField(max_length=24,choices=STATUSES,default='draft')
    delivery_date=models.DateField(null=True,blank=True); delivery_region=models.ForeignKey(DeliveryRegion,on_delete=models.PROTECT,null=True,blank=True)
    delivery_address=models.TextField(blank=True); delivery_fee=models.DecimalField(max_digits=8,decimal_places=2,default=0); subtotal=models.DecimalField(max_digits=12,decimal_places=2,default=0); discount=models.DecimalField(max_digits=10,decimal_places=2,default=0); total=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    customer_note=models.TextField(blank=True); internal_note=models.TextField(blank=True)
    def __str__(self): return f'#{str(self.public_id)[:8]} - {self.customer}'

class OrderItem(TimeStamped):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name='items'); product=models.ForeignKey(Product,on_delete=models.PROTECT)
    quantity=models.PositiveIntegerField(validators=[MinValueValidator(1)]); unit_price=models.DecimalField(max_digits=10,decimal_places=2); note=models.CharField(max_length=250,blank=True)
    @property
    def total(self): return self.unit_price*self.quantity

class OrderStatusHistory(TimeStamped):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name='status_history'); status=models.CharField(max_length=24,choices=Order.STATUSES); changed_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True); note=models.CharField(max_length=250,blank=True)

class Payment(TimeStamped):
    STATUSES=[('pending','Pendente'),('approved','Aprovado'),('rejected','Rejeitado'),('refunded','Estornado'),('cancelled','Cancelado')]
    order=models.ForeignKey(Order,on_delete=models.PROTECT,related_name='payments'); provider=models.CharField(max_length=30,default='mercado_pago'); provider_id=models.CharField(max_length=160,blank=True,db_index=True)
    status=models.CharField(max_length=16,choices=STATUSES,default='pending'); amount=models.DecimalField(max_digits=12,decimal_places=2); method=models.CharField(max_length=30,blank=True); paid_at=models.DateTimeField(null=True,blank=True)
    raw_reference=models.JSONField(default=dict,blank=True,help_text='Somente IDs/status não sensíveis. Nunca armazenar cartão.')

class Conversation(TimeStamped):
    order=models.OneToOneField(Order,on_delete=models.CASCADE,related_name='conversation'); customer=models.ForeignKey(User,on_delete=models.CASCADE,related_name='conversations'); closed=models.BooleanField(default=False)

class Message(TimeStamped):
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages'); sender=models.ForeignKey(User,on_delete=models.PROTECT,related_name='sent_store_messages')
    body=models.TextField(max_length=4000); read_at=models.DateTimeField(null=True,blank=True)
    class Meta: ordering=['created_at']

class Promotion(TimeStamped):
    AUDIENCES=[('all','Todos'),('retail','Clientes'),('cafe','Cafeterias'),('event','Eventos'),('loyal','Clientes recorrentes')]
    name=models.CharField(max_length=120); code=models.CharField(max_length=40,unique=True); audience=models.CharField(max_length=12,choices=AUDIENCES,default='all')
    percent_off=models.DecimalField(max_digits=5,decimal_places=2,default=0); minimum_orders=models.PositiveIntegerField(default=0); minimum_spend=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    active=models.BooleanField(default=True); starts_at=models.DateTimeField(); ends_at=models.DateTimeField()
