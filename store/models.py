import uuid
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

class TimeStamped(models.Model):
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: abstract=True

class CustomerProfile(TimeStamped):
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Eventos')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='customer_profile')
    customer_type=models.CharField(max_length=12,choices=TYPES,default='retail')
    phone=models.CharField(max_length=24,blank=True)
    birth_date=models.DateField(null=True,blank=True)
    marketing_opt_in=models.BooleanField(default=False)
    orders_count=models.PositiveIntegerField(default=0)
    lifetime_value=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    notes=models.TextField(blank=True,help_text='Somente equipe interna.')
    def __str__(self): return self.user.get_full_name() or self.user.username

class CustomerAddress(TimeStamped):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='saved_addresses')
    label=models.CharField(max_length=60,default='Principal')
    zip_code=models.CharField(max_length=10)
    street=models.CharField(max_length=180)
    number=models.CharField(max_length=30)
    complement=models.CharField(max_length=100,blank=True)
    neighborhood=models.CharField(max_length=120,blank=True)
    city=models.CharField(max_length=120,default='Rio de Janeiro')
    default=models.BooleanField(default=False)
    def __str__(self): return f'{self.label} - {self.street}, {self.number}'

class Category(TimeStamped):
    name=models.CharField(max_length=100)
    slug=models.SlugField(unique=True)
    description=models.TextField(blank=True)
    image=models.ImageField(upload_to='categories/',blank=True,null=True)
    active=models.BooleanField(default=True)
    sort_order=models.PositiveIntegerField(default=0)
    class Meta: ordering=['sort_order','name']; verbose_name_plural='Categorias'
    def __str__(self): return self.name

class Product(TimeStamped):
    category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name='products')
    name=models.CharField(max_length=140)
    slug=models.SlugField(unique=True)
    description=models.TextField()
    image=models.ImageField(upload_to='products/')
    active=models.BooleanField(default=True)
    featured=models.BooleanField(default=False)
    sell_retail=models.BooleanField(default=True)
    sell_cafe=models.BooleanField(default=True)
    sell_event=models.BooleanField(default=True)
    min_quantity=models.PositiveIntegerField(default=1)
    lead_time_days=models.PositiveIntegerField(default=1)
    stock_limit=models.PositiveIntegerField(null=True,blank=True)
    sort_order=models.PositiveIntegerField(default=0)
    class Meta: ordering=['category__sort_order','sort_order','name']
    def __str__(self): return self.name

class ProductImage(TimeStamped):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='gallery')
    image=models.ImageField(upload_to='products/gallery/')
    alt_text=models.CharField(max_length=180,blank=True)
    sort_order=models.PositiveIntegerField(default=0)
    class Meta: ordering=['sort_order','id']


class BrandProfile(TimeStamped):
    """Small, public-facing facts about the people behind the brand."""
    owner_names=models.CharField(max_length=220,blank=True,help_text='Nomes dos donos/fundadores exibidos no site público.')
    operating_since=models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1800), MaxValueValidator(2100)],
        help_text='Ano em que a Nossas Delícias começou a funcionar.',
    )
    location=models.CharField(max_length=160,blank=True,help_text='Cidade, bairro ou região exibida no site público.')
    class Meta:
        verbose_name='Informações da marca'
        verbose_name_plural='Informações da marca'
    def __str__(self): return 'Informações públicas da Nossas Delícias'


class CafeLocation(TimeStamped):
    """A public delivery-partner card. It intentionally does not expose B2B account data."""
    slot=models.PositiveSmallIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text='Posição da cafeteria na vitrine pública (de 1 a 6).',
    )
    name=models.CharField(max_length=160,blank=True)
    location=models.CharField(max_length=180,blank=True,help_text='Bairro, cidade ou endereço resumido para o público.')
    rating=models.DecimalField(
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))],
        help_text='Nota pública de 1,0 a 5,0.',
    )
    logo=models.ImageField(upload_to='cafes/logos/',blank=True)
    delivery_note=models.CharField(max_length=180,blank=True,help_text='Ex.: entrega por aplicativo, retirada ou dias atendidos.')
    class Meta:
        ordering=['slot']
        verbose_name='Cafeteria parceira pública'
        verbose_name_plural='Cafeterias parceiras públicas'
        constraints=[
            models.CheckConstraint(
                condition=models.Q(slot__gte=1, slot__lte=6),
                name='cafe_location_slot_between_1_and_6',
            ),
        ]
    def __str__(self): return self.name or f'Cafeteria parceira {self.slot:02d}'

class Favorite(TimeStamped):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='favorite_products')
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='favorited_by')
    class Meta:
        unique_together=('user','product')
        ordering=['-created_at']
    def __str__(self): return f'{self.user} · {self.product}'

class PriceTable(TimeStamped):
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Eventos'),('custom','Personalizada')]
    name=models.CharField(max_length=100)
    kind=models.CharField(max_length=12,choices=TYPES)
    active=models.BooleanField(default=True)
    assigned_users=models.ManyToManyField(User,blank=True,related_name='price_tables')
    def __str__(self): return self.name

class ProductPrice(TimeStamped):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='prices')
    table=models.ForeignKey(PriceTable,on_delete=models.CASCADE,related_name='prices')
    min_quantity=models.PositiveIntegerField(default=1)
    unit_price=models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(Decimal('0.01'))])
    class Meta: ordering=['product','table','min_quantity']; unique_together=('product','table','min_quantity')

class CafeAccount(TimeStamped):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='cafe_account')
    business_name=models.CharField(max_length=160)
    contact_name=models.CharField(max_length=140,blank=True)
    document=models.CharField(max_length=30,blank=True,help_text='Evite coletar documento se não for necessário à operação.')
    approved=models.BooleanField(default=False)
    active=models.BooleanField(default=True)
    minimum_order=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    price_table=models.ForeignKey(PriceTable,on_delete=models.SET_NULL,null=True,blank=True,limit_choices_to={'kind__in':['cafe','custom']})
    internal_note=models.TextField(blank=True)
    def __str__(self): return self.business_name

class DeliveryRegion(TimeStamped):
    name=models.CharField(max_length=120)
    active=models.BooleanField(default=True)
    delivery_fee=models.DecimalField(max_digits=8,decimal_places=2,default=0)
    minimum_order=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    zip_prefixes=models.TextField(blank=True,help_text='Prefixos de CEP separados por vírgula.')
    def __str__(self): return self.name
    def matches_zip(self,value):
        digits=''.join(filter(str.isdigit,value or ''))
        return any(digits.startswith(p.strip()) for p in self.zip_prefixes.split(',') if p.strip())

class DeliveryRoute(TimeStamped):
    name=models.CharField(max_length=120)
    regions=models.ManyToManyField(DeliveryRegion,related_name='routes')
    active=models.BooleanField(default=True)
    weekdays=models.CharField(max_length=20,help_text='0=segunda ... 6=domingo. Ex: 1,3,5')
    default_capacity=models.PositiveIntegerField(default=30)
    start_time=models.TimeField()
    end_time=models.TimeField()
    def weekday_set(self): return {int(v) for v in self.weekdays.split(',') if v.strip().isdigit()}
    def __str__(self): return self.name

class AvailabilityDay(TimeStamped):
    date=models.DateField(unique=True)
    enabled=models.BooleanField(default=True)
    capacity=models.PositiveIntegerField(default=30)
    note=models.CharField(max_length=200,blank=True)
    def __str__(self): return str(self.date)

class Cart(TimeStamped):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='cart')
    def __str__(self): return f'Carrinho - {self.user}'

class CartItem(TimeStamped):
    cart=models.ForeignKey(Cart,on_delete=models.CASCADE,related_name='items')
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    quantity=models.PositiveIntegerField(default=1,validators=[MinValueValidator(1)])
    note=models.CharField(max_length=250,blank=True)
    class Meta: unique_together=('cart','product')

class Order(TimeStamped):
    STATUSES=[('draft','Rascunho'),('pending_payment','Aguardando pagamento'),('paid','Pago'),('production','Em produção'),('ready','Pronto'),('delivery','Saiu para entrega'),('completed','Concluído'),('cancelled','Cancelado')]
    TYPES=[('retail','Cliente'),('cafe','Cafeteria'),('event','Evento')]
    public_id=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    customer=models.ForeignKey(User,on_delete=models.PROTECT,related_name='orders')
    order_type=models.CharField(max_length=12,choices=TYPES,default='retail')
    status=models.CharField(max_length=24,choices=STATUSES,default='draft')
    delivery_date=models.DateField(null=True,blank=True)
    delivery_region=models.ForeignKey(DeliveryRegion,on_delete=models.PROTECT,null=True,blank=True)
    delivery_address=models.TextField(blank=True)
    delivery_fee=models.DecimalField(max_digits=8,decimal_places=2,default=0)
    subtotal=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    discount=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    total=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    promotion_code=models.CharField(max_length=40,blank=True)
    customer_note=models.TextField(blank=True)
    internal_note=models.TextField(blank=True)
    def __str__(self): return f'#{str(self.public_id)[:8]} - {self.customer}'

class OrderItem(TimeStamped):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name='items')
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    quantity=models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price=models.DecimalField(max_digits=10,decimal_places=2)
    note=models.CharField(max_length=250,blank=True)
    @property
    def total(self): return self.unit_price*self.quantity

class OrderStatusHistory(TimeStamped):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name='status_history')
    status=models.CharField(max_length=24,choices=Order.STATUSES)
    changed_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    note=models.CharField(max_length=250,blank=True)

class Payment(TimeStamped):
    STATUSES=[('pending','Pendente'),('approved','Aprovado'),('rejected','Rejeitado'),('refunded','Estornado'),('cancelled','Cancelado')]
    order=models.ForeignKey(Order,on_delete=models.PROTECT,related_name='payments')
    provider=models.CharField(max_length=30,default='mercado_pago')
    provider_id=models.CharField(max_length=160,blank=True,db_index=True)
    status=models.CharField(max_length=16,choices=STATUSES,default='pending')
    amount=models.DecimalField(max_digits=12,decimal_places=2)
    method=models.CharField(max_length=30,blank=True)
    paid_at=models.DateTimeField(null=True,blank=True)
    raw_reference=models.JSONField(default=dict,blank=True,help_text='Somente IDs/status não sensíveis. Nunca armazenar cartão.')

class Conversation(TimeStamped):
    order=models.OneToOneField(Order,on_delete=models.CASCADE,related_name='conversation')
    customer=models.ForeignKey(User,on_delete=models.CASCADE,related_name='conversations')
    closed=models.BooleanField(default=False)

class Message(TimeStamped):
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages')
    sender=models.ForeignKey(User,on_delete=models.PROTECT,related_name='sent_store_messages')
    body=models.TextField(max_length=4000)
    read_at=models.DateTimeField(null=True,blank=True)
    class Meta: ordering=['created_at']


class DataSubjectRequest(TimeStamped):
    """A tracked, human-reviewed channel for LGPD data-subject requests."""
    TYPES = [
        ('access', 'Acesso ou cópia dos dados'),
        ('correction', 'Correção de dados'),
        ('deletion', 'Eliminação ou anonimização'),
        ('portability', 'Portabilidade'),
        ('consent', 'Revogação de consentimento'),
        ('information', 'Informações sobre tratamento'),
    ]
    STATUSES = [
        ('new', 'Nova'),
        ('review', 'Em análise'),
        ('waiting', 'Aguardando confirmação'),
        ('resolved', 'Concluída'),
        ('rejected', 'Não aplicável'),
    ]
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    requester = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='data_subject_requests')
    email = models.EmailField()
    request_type = models.CharField(max_length=20, choices=TYPES)
    details = models.TextField(max_length=1200, blank=True)
    status = models.CharField(max_length=16, choices=STATUSES, default='new', db_index=True)
    resolution_note = models.TextField(max_length=1200, blank=True, help_text='Somente equipe interna.')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_data_subject_requests')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['status', '-created_at']
        indexes = [models.Index(fields=['status', 'created_at'])]
        verbose_name = 'Solicitação de dados (LGPD)'
        verbose_name_plural = 'Solicitações de dados (LGPD)'

    def __str__(self):
        return f'{self.get_request_type_display()} · {self.email}'

class Promotion(TimeStamped):
    AUDIENCES=[('all','Todos'),('retail','Clientes'),('cafe','Cafeterias'),('event','Eventos'),('loyal','Clientes recorrentes')]
    name=models.CharField(max_length=120)
    code=models.CharField(max_length=40,unique=True)
    audience=models.CharField(max_length=12,choices=AUDIENCES,default='all')
    percent_off=models.DecimalField(max_digits=5,decimal_places=2,default=0,validators=[MinValueValidator(Decimal('0')),MaxValueValidator(Decimal('100'))])
    minimum_orders=models.PositiveIntegerField(default=0)
    minimum_spend=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    max_uses_per_user=models.PositiveIntegerField(default=1)
    active=models.BooleanField(default=True)
    starts_at=models.DateTimeField()
    ends_at=models.DateTimeField()

class PromotionRedemption(TimeStamped):
    promotion=models.ForeignKey(Promotion,on_delete=models.PROTECT,related_name='redemptions')
    user=models.ForeignKey(User,on_delete=models.PROTECT,related_name='promotion_redemptions')
    order=models.OneToOneField(Order,on_delete=models.PROTECT,related_name='promotion_redemption')
    discount_amount=models.DecimalField(max_digits=10,decimal_places=2)

class EventQuote(TimeStamped):
    STATUSES=[('new','Novo'),('review','Em análise'),('sent','Proposta enviada'),('negotiation','Em negociação'),('accepted','Aceito'),('converted','Convertido em pedido'),('production','Em produção'),('completed','Concluído'),('declined','Recusado')]
    TYPES=[('birthday','Aniversário'),('wedding','Casamento'),('corporate','Corporativo'),('party','Festa'),('other','Outro')]
    public_id=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    customer=models.ForeignKey(User,on_delete=models.PROTECT,related_name='event_quotes')
    event_type=models.CharField(max_length=20,choices=TYPES,default='other')
    event_date=models.DateField()
    guest_count=models.PositiveIntegerField(default=1)
    address=models.CharField(max_length=240,blank=True)
    notes=models.TextField(blank=True)
    status=models.CharField(max_length=20,choices=STATUSES,default='new')
    estimated_total=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    final_total=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    converted_order=models.OneToOneField(Order,on_delete=models.SET_NULL,null=True,blank=True,related_name='source_quote')
    def __str__(self): return f'Evento #{str(self.public_id)[:8]} - {self.customer}'

class EventQuoteItem(TimeStamped):
    quote=models.ForeignKey(EventQuote,on_delete=models.CASCADE,related_name='items')
    product=models.ForeignKey(Product,on_delete=models.PROTECT,null=True,blank=True)
    description=models.CharField(max_length=200,blank=True)
    quantity=models.PositiveIntegerField(default=1)
    proposed_unit_price=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)

class CakeOption(TimeStamped):
    KINDS=[('dough','Massa'),('filling','Recheio'),('complement','Complemento'),('frosting','Cobertura')]
    kind=models.CharField(max_length=16,choices=KINDS,db_index=True)
    name=models.CharField(max_length=120)
    slug=models.SlugField(max_length=140)
    description=models.CharField(max_length=220,blank=True)
    preview_color=models.CharField(max_length=20,default='#d9a77f',help_text='Cor usada apenas na prévia visual do configurador.')
    active=models.BooleanField(default=True)
    sort_order=models.PositiveIntegerField(default=0)
    class Meta:
        ordering=['kind','sort_order','name']
        unique_together=('kind','slug')
        verbose_name='Opção de bolo'
        verbose_name_plural='Opções de bolo'
    def __str__(self): return f'{self.get_kind_display()} · {self.name}'

class CakeDesign(TimeStamped):
    DECORATION_STYLES=[('classic','Clássico artesanal'),('vintage','Vintage'),('minimal','Minimalista'),('floral','Floral delicado'),('themed','Tema personalizado')]
    quote=models.OneToOneField(EventQuote,on_delete=models.CASCADE,related_name='cake_design')
    dough=models.ForeignKey(CakeOption,on_delete=models.PROTECT,related_name='cake_doughs',limit_choices_to={'kind':'dough'})
    primary_filling=models.ForeignKey(CakeOption,on_delete=models.PROTECT,related_name='cake_primary_fillings',limit_choices_to={'kind':'filling'})
    secondary_filling=models.ForeignKey(CakeOption,on_delete=models.PROTECT,related_name='cake_secondary_fillings',limit_choices_to={'kind':'filling'},null=True,blank=True)
    complement=models.ForeignKey(CakeOption,on_delete=models.PROTECT,related_name='cake_complements',limit_choices_to={'kind':'complement'},null=True,blank=True)
    frosting=models.ForeignKey(CakeOption,on_delete=models.PROTECT,related_name='cake_frostings',limit_choices_to={'kind':'frosting'})
    decoration_style=models.CharField(max_length=16,choices=DECORATION_STYLES,default='classic')
    decoration_notes=models.TextField(blank=True,max_length=1200)
    occasion=models.CharField(max_length=120,blank=True)
    reference_image=models.ImageField(upload_to='events/cake-references/',blank=True,null=True)
    selection_snapshot=models.JSONField(default=dict,blank=True,editable=False)
    def __str__(self): return f'Bolo · evento #{str(self.quote.public_id)[:8]}'

class EventQuoteStatusHistory(TimeStamped):
    quote=models.ForeignKey(EventQuote,on_delete=models.CASCADE,related_name='status_history')
    status=models.CharField(max_length=20,choices=EventQuote.STATUSES)
    changed_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    note=models.CharField(max_length=250,blank=True)
    class Meta: ordering=['created_at']

class EventQuoteMessage(TimeStamped):
    quote=models.ForeignKey(EventQuote,on_delete=models.CASCADE,related_name='messages')
    sender=models.ForeignKey(User,on_delete=models.PROTECT,related_name='sent_event_messages')
    body=models.TextField(max_length=4000)
    read_at=models.DateTimeField(null=True,blank=True)
    class Meta: ordering=['created_at']
    def __str__(self): return f'Evento {str(self.quote.public_id)[:8]} · {self.sender}'

class RecurringOrder(TimeStamped):
    cafe=models.ForeignKey(CafeAccount,on_delete=models.CASCADE,related_name='recurring_orders')
    name=models.CharField(max_length=120,default='Pedido semanal')
    weekday=models.PositiveSmallIntegerField(validators=[MinValueValidator(0),MaxValueValidator(6)])
    active=models.BooleanField(default=True)
    delivery_region=models.ForeignKey(DeliveryRegion,on_delete=models.PROTECT)
    delivery_address=models.CharField(max_length=240)
    note=models.CharField(max_length=250,blank=True)
    def __str__(self): return f'{self.cafe} - {self.name}'

class RecurringOrderItem(TimeStamped):
    recurring_order=models.ForeignKey(RecurringOrder,on_delete=models.CASCADE,related_name='items')
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    quantity=models.PositiveIntegerField(default=1)
    note=models.CharField(max_length=250,blank=True)
    class Meta: unique_together=('recurring_order','product')
