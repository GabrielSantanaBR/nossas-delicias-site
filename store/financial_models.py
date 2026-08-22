from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

MONEY = Decimal('0.01')


class FinancialTimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProductCostProfile(FinancialTimeStamped):
    """Financial metadata imported/calculated from the pricing spreadsheet.

    Prices offered to customers live in ProductPrice. This model is intentionally
    separate: changing an ingredient or recipe cost must not rewrite historical sales.
    Historical orders use OrderItemFinancialSnapshot below.
    """

    SALE_UNITS = [
        ('unit', 'Unidade'),
        ('slice', 'Fatia'),
        ('portion', 'Grama/porção'),
        ('box', 'Caixa/kit'),
        ('other', 'Outro'),
    ]

    product = models.OneToOneField('store.Product', on_delete=models.CASCADE, related_name='cost_profile')
    sku = models.CharField(max_length=40, unique=True, db_index=True)
    sale_unit = models.CharField(max_length=16, choices=SALE_UNITS, default='unit')
    yield_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, validators=[MinValueValidator(Decimal('0.001'))])
    production_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, validators=[MinValueValidator(Decimal('0'))])
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, validators=[MinValueValidator(Decimal('0'))])
    source_reference = models.CharField(max_length=120, blank=True, help_text='Ex.: Planilha Automatizada 4.0 / REC-001')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sku']
        verbose_name = 'Custo do produto'
        verbose_name_plural = 'Custos dos produtos'

    def save(self, *args, **kwargs):
        if self.yield_quantity and self.production_cost is not None:
            self.unit_cost = (self.production_cost / self.yield_quantity).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.sku} - {self.product}'


class OrderItemFinancialSnapshot(FinancialTimeStamped):
    """Frozen financial values for an order line.

    While an editable cafeteria order changes, this row is refreshed. Once the
    cafeteria delivery note reaches its cutoff, these rows become historical facts.
    """

    order_item = models.OneToOneField('store.OrderItem', on_delete=models.CASCADE, related_name='financial_snapshot')
    sku = models.CharField(max_length=40, blank=True)
    product_name = models.CharField(max_length=180)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    profit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    margin_percent = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    cost_missing = models.BooleanField(default=False)

    class Meta:
        ordering = ['order_item__order_id', 'order_item_id']
        verbose_name = 'Snapshot financeiro do item'
        verbose_name_plural = 'Snapshots financeiros dos itens'

    def __str__(self):
        return f'{self.product_name} - {self.quantity} un.'


class CafeDeliveryNote(FinancialTimeStamped):
    STATUSES = [('draft', 'Editável'), ('locked', 'Fechada'), ('cancelled', 'Cancelada')]

    order = models.OneToOneField('store.Order', on_delete=models.PROTECT, related_name='cafe_delivery_note')
    note_number = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='draft')
    editable_until = models.DateTimeField()
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_cafe_notes')
    quantity_snapshot = models.PositiveIntegerField(default=0)
    revenue_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    profit_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    margin_snapshot = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    payment_snapshot = models.CharField(max_length=40, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-order__delivery_date', '-created_at']
        verbose_name = 'Nota de entrega da cafeteria'
        verbose_name_plural = 'Notas de entrega das cafeterias'

    @staticmethod
    def cutoff_for(order):
        if not order.delivery_date:
            return timezone.now()
        naive = datetime.combine(order.delivery_date, time(hour=16, minute=0))
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def is_locked(self):
        return self.status == 'locked' or self.locked_at is not None or timezone.now() >= self.editable_until

    def clean(self):
        if self.order_id and self.order.order_type != 'cafe':
            raise ValidationError('Notas de cafeteria só podem ser vinculadas a pedidos do tipo cafeteria.')

    def save(self, *args, **kwargs):
        if self.order_id and not self.editable_until:
            self.editable_until = self.cutoff_for(self.order)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.note_number


class BusinessExpense(FinancialTimeStamped):
    CATEGORIES = [
        ('ingredient', 'Ingredientes'),
        ('packaging', 'Embalagens'),
        ('logistics', 'Logística/entrega'),
        ('utilities', 'Água, luz, gás e internet'),
        ('marketing', 'Marketing'),
        ('equipment', 'Equipamentos/manutenção'),
        ('fees', 'Taxas e serviços'),
        ('other', 'Outros'),
    ]
    PAYMENT_STATUSES = [('pending', 'Pendente'), ('paid', 'Pago'), ('cancelled', 'Cancelado')]

    date = models.DateField(default=timezone.localdate, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='other')
    description = models.CharField(max_length=180)
    supplier = models.CharField(max_length=140, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_status = models.CharField(max_length=12, choices=PAYMENT_STATUSES, default='paid')
    payment_method = models.CharField(max_length=40, blank=True)
    attachment = models.FileField(upload_to='finance/expenses/', blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='business_expenses_created')

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Despesa do negócio'
        verbose_name_plural = 'Despesas do negócio'

    def __str__(self):
        return f'{self.date:%d/%m/%Y} - {self.description}'
