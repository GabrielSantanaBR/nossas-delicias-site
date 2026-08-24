from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CustomerProfile(models.Model):
    class CustomerType(models.TextChoices):
        RETAIL = "retail", "Cliente"
        CAFE = "cafe", "Cafeteria"
        EVENT = "event", "Evento"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    customer_type = models.CharField(max_length=12, choices=CustomerType.choices, default=CustomerType.RETAIL)
    phone = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name or self.user.get_full_name() or self.user.username


class ProductCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True)
    active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    minimum_quantity = models.PositiveIntegerField(default=1)
    lead_time_hours = models.PositiveIntegerField(default=24)
    production_units = models.PositiveIntegerField(default=1, help_text="Peso de capacidade para a agenda")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    customer_type = models.CharField(max_length=12, choices=CustomerProfile.CustomerType.choices)
    min_quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product", "customer_type", "min_quantity"]
        unique_together = ("product", "customer_type", "min_quantity")

    def __str__(self):
        return f"{self.product} - {self.get_customer_type_display()} - {self.price}"


class DeliveryRegion(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    neighborhoods = models.TextField(blank=True, help_text="Bairros separados por vírgula; use como apoio, não como validação única.")
    postal_code_start = models.CharField(max_length=9, blank=True)
    postal_code_end = models.CharField(max_length=9, blank=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    minimum_order = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "city", "name"]

    def __str__(self):
        return f"{self.name} ({self.city})"


class DeliveryRoute(models.Model):
    name = models.CharField(max_length=100)
    regions = models.ManyToManyField(DeliveryRegion, related_name="routes")
    weekday = models.PositiveSmallIntegerField(choices=[
        (0, "Segunda"), (1, "Terça"), (2, "Quarta"), (3, "Quinta"),
        (4, "Sexta"), (5, "Sábado"), (6, "Domingo"),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_orders = models.PositiveIntegerField(default=30)
    max_capacity_units = models.PositiveIntegerField(default=300)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.get_weekday_display()}"


class DeliverySlot(models.Model):
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField()
    blocked = models.BooleanField(default=False)
    capacity_percent = models.PositiveSmallIntegerField(default=100)
    note = models.CharField(max_length=180, blank=True)

    class Meta:
        unique_together = ("route", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.route} - {self.date}"


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PENDING = "pending", "Aguardando confirmação"
        CONFIRMED = "confirmed", "Confirmado"
        PRODUCTION = "production", "Em produção"
        READY = "ready", "Pronto"
        DELIVERY = "delivery", "Saiu para entrega"
        COMPLETED = "completed", "Entregue"
        CANCELLED = "cancelled", "Cancelado"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    customer_type = models.CharField(max_length=12, choices=CustomerProfile.CustomerType.choices, default=CustomerProfile.CustomerType.RETAIL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    delivery_region = models.ForeignKey(DeliveryRegion, on_delete=models.PROTECT, null=True, blank=True)
    delivery_slot = models.ForeignKey(DeliverySlot, on_delete=models.PROTECT, null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    postal_code = models.CharField(max_length=9, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    customer_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ND-{self.pk or 'novo'}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)

    @property
    def total(self):
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=16, choices=Order.Status.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Conversation(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Pago"
        FAILED = "failed", "Falhou"
        REFUNDED = "refunded", "Reembolsado"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    provider = models.CharField(max_length=40, default="disabled")
    provider_reference = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order} - {self.status}"
