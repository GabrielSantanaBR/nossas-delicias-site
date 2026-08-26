from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

CENT = Decimal('0.01')
FOUR = Decimal('0.0001')


class Ingredient(models.Model):
    UNIT_CHOICES = [
        ('g', 'Grama'), ('ml', 'Mililitro'), ('un', 'Unidade'),
        ('kg', 'Quilograma'), ('l', 'Litro'), ('other', 'Outro'),
    ]

    code = models.CharField(max_length=24, unique=True, db_index=True)
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=100, blank=True)
    package_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    package_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1, validators=[MinValueValidator(Decimal('0.0001'))])
    base_unit = models.CharField(max_length=12, choices=UNIT_CHOICES, default='g')
    unit_cost = models.DecimalField(max_digits=14, decimal_places=6, default=0, editable=False)
    supplier = models.CharField(max_length=140, blank=True)
    aliases = models.TextField(blank=True, help_text='Nomes alternativos separados por |.')
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=4, default=0, validators=[MinValueValidator(Decimal('0'))])
    last_price_update = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Ingrediente / insumo'
        verbose_name_plural = 'Ingredientes / insumos'

    def save(self, *args, **kwargs):
        if self.package_quantity:
            self.unit_cost = (Decimal(self.package_price or 0) / Decimal(self.package_quantity)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        else:
            self.unit_cost = Decimal('0')
        super().save(*args, **kwargs)

    @property
    def stock_balance(self):
        value = self.movements.aggregate(total=Sum('quantity_delta'))['total'] or Decimal('0')
        return Decimal(value).quantize(FOUR, rounding=ROUND_HALF_UP)

    @property
    def stock_status(self):
        if self.minimum_stock and self.stock_balance <= self.minimum_stock:
            return 'low'
        return 'ok'

    def __str__(self):
        return f'{self.code} - {self.name}'


class IngredientPriceHistory(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='price_history')
    package_price = models.DecimalField(max_digits=12, decimal_places=2)
    package_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=6)
    supplier = models.CharField(max_length=140, blank=True)
    source = models.CharField(max_length=160, blank=True)
    effective_date = models.DateField(default=timezone.localdate, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-effective_date', '-created_at']
        verbose_name = 'Histórico de preço de ingrediente'
        verbose_name_plural = 'Histórico de preços de ingredientes'


class InventoryMovement(models.Model):
    TYPES = [
        ('purchase', 'Compra/entrada'),
        ('production', 'Consumo em produção'),
        ('waste', 'Perda/descarte'),
        ('adjustment', 'Ajuste de estoque'),
        ('return', 'Devolução/estorno'),
    ]
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=16, choices=TYPES)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=4, help_text='Entrada positiva; consumo/perda negativo.')
    unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    date = models.DateField(default=timezone.localdate, db_index=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Movimentação de estoque'
        verbose_name_plural = 'Movimentações de estoque'

    def save(self, *args, **kwargs):
        if self.unit_cost_snapshot is None and self.ingredient_id:
            self.unit_cost_snapshot = self.ingredient.unit_cost
        if self.movement_type in {'production', 'waste'} and self.quantity_delta > 0:
            self.quantity_delta = -self.quantity_delta
        super().save(*args, **kwargs)


class Recipe(models.Model):
    SALE_UNITS = [
        ('unit', 'Unidade'), ('slice', 'Fatia'), ('portion', 'Grama/porção'),
        ('box', 'Caixa/kit'), ('other', 'Outro'),
    ]
    code = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=100, blank=True)
    sale_unit = models.CharField(max_length=16, choices=SALE_UNITS, default='unit')
    yield_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, validators=[MinValueValidator(Decimal('0.001'))])
    extra_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, validators=[MinValueValidator(Decimal('0'))])
    imported_production_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))])
    product = models.OneToOneField('store.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='recipe')
    active = models.BooleanField(default=True)
    source_reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'code']
        verbose_name = 'Receita / ficha técnica'
        verbose_name_plural = 'Receitas / fichas técnicas'

    @property
    def calculated_ingredient_cost(self):
        total = Decimal('0')
        for row in self.ingredients.select_related('ingredient').all():
            multiplier = Decimal('1') + (Decimal(row.waste_percent or 0) / Decimal('100'))
            total += Decimal(row.quantity_used) * Decimal(row.ingredient.unit_cost) * multiplier
        return total.quantize(FOUR, rounding=ROUND_HALF_UP)

    @property
    def production_cost(self):
        if self.ingredients.exists():
            return (self.calculated_ingredient_cost + Decimal(self.extra_cost or 0)).quantize(FOUR, rounding=ROUND_HALF_UP)
        return Decimal(self.imported_production_cost or self.extra_cost or 0).quantize(FOUR, rounding=ROUND_HALF_UP)

    @property
    def unit_cost(self):
        if not self.yield_quantity:
            return Decimal('0')
        return (self.production_cost / Decimal(self.yield_quantity)).quantize(FOUR, rounding=ROUND_HALF_UP)

    def __str__(self):
        return f'{self.code} - {self.name}'


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='recipe_uses')
    quantity_used = models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    waste_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    notes = models.CharField(max_length=220, blank=True)

    class Meta:
        unique_together = ('recipe', 'ingredient')
        ordering = ['recipe', 'ingredient__name']
        verbose_name = 'Ingrediente da receita'
        verbose_name_plural = 'Ingredientes das receitas'

    @property
    def total_cost(self):
        multiplier = Decimal('1') + (Decimal(self.waste_percent or 0) / Decimal('100'))
        return (Decimal(self.quantity_used) * Decimal(self.ingredient.unit_cost) * multiplier).quantize(FOUR, rounding=ROUND_HALF_UP)


class FinancialSettings(models.Model):
    desired_margin_percent = models.DecimalField(max_digits=6, decimal_places=2, default=30, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('95'))])
    payment_fee_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))])
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))])
    contingency_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração financeira'
        verbose_name_plural = 'Configuração financeira'

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def recommended_price(self, unit_cost, desired_margin=None):
        margin = Decimal(desired_margin if desired_margin is not None else self.desired_margin_percent) / Decimal('100')
        fees = (Decimal(self.payment_fee_percent) + Decimal(self.tax_percent) + Decimal(self.contingency_percent)) / Decimal('100')
        denominator = Decimal('1') - margin - fees
        if denominator <= Decimal('0'):
            return None
        return (Decimal(unit_cost or 0) / denominator).quantize(CENT, rounding=ROUND_HALF_UP)


class FixedCost(models.Model):
    CATEGORIES = [
        ('rent', 'Aluguel'), ('utilities', 'Água, luz, gás e internet'),
        ('payroll', 'Pessoal/pró-labore'), ('software', 'Sistemas e assinaturas'),
        ('marketing', 'Marketing'), ('logistics', 'Logística'), ('other', 'Outros'),
    ]
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='other')
    monthly_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    due_day = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(28)])
    active = models.BooleanField(default=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_day', 'name']
        verbose_name = 'Custo fixo / recorrente'
        verbose_name_plural = 'Custos fixos / recorrentes'


class SpreadsheetImportBatch(models.Model):
    STATUSES = [('success', 'Concluído'), ('partial', 'Parcial'), ('failed', 'Falhou')]
    filename = models.CharField(max_length=180)
    sha256 = models.CharField(max_length=64, db_index=True)
    source_version = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES)
    ingredients_created = models.PositiveIntegerField(default=0)
    ingredients_updated = models.PositiveIntegerField(default=0)
    recipes_created = models.PositiveIntegerField(default=0)
    recipes_updated = models.PositiveIntegerField(default=0)
    prices_updated = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Importação de planilha'
        verbose_name_plural = 'Importações de planilha'
