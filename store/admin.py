from django.contrib import admin
from .models import (
    Conversation, CustomerProfile, DeliveryRegion, DeliveryRoute, DeliverySlot,
    Message, Order, OrderItem, OrderStatusHistory, Payment, Product,
    ProductCategory, ProductPrice,
)

admin.site.site_header = "Nossas Delícias • Central de Operações"
admin.site.site_title = "Nossas Delícias"
admin.site.index_title = "Pedidos, produtos, preços, rotas e atendimento"


class ProductPriceInline(admin.TabularInline):
    model = ProductPrice
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "active", "featured", "lead_time_hours")
    list_filter = ("active", "featured", "category")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductPriceInline]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "position")
    list_editable = ("active", "position")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DeliveryRegion)
class DeliveryRegionAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "delivery_fee", "minimum_order", "active", "position")
    list_editable = ("delivery_fee", "minimum_order", "active", "position")
    list_filter = ("city", "active")
    search_fields = ("name", "city", "neighborhoods", "postal_code_start", "postal_code_end")


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ("name", "weekday", "start_time", "end_time", "max_orders", "max_capacity_units", "active")
    list_editable = ("start_time", "end_time", "max_orders", "max_capacity_units", "active")
    filter_horizontal = ("regions",)


@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ("date", "route", "blocked", "capacity_percent", "note")
    list_editable = ("blocked", "capacity_percent")
    list_filter = ("blocked", "route")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("unit_price",)


class OrderStatusInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "customer_type", "status", "delivery_region", "total", "created_at")
    list_filter = ("status", "customer_type", "delivery_region")
    search_fields = ("customer__username", "customer__email", "postal_code", "delivery_address")
    readonly_fields = ("created_at", "updated_at")
    inlines = [OrderItemInline, OrderStatusInline]


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "customer_type", "company_name", "phone", "active")
    list_filter = ("customer_type", "active")
    search_fields = ("user__username", "user__email", "company_name", "phone")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "status", "amount", "updated_at")
    list_filter = ("provider", "status")
    readonly_fields = ("provider_reference", "created_at", "updated_at")


admin.site.register(Conversation)
admin.site.register(Message)
