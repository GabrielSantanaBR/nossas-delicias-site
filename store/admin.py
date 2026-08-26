from django.contrib import admin
from .admin_site import secure_admin_site
from .models import *
from .financial_models import BusinessExpense, CafeDeliveryNote, OrderItemFinancialSnapshot, ProductCostProfile
from .financial_services import cafe_order_editable, lock_cafe_note, maybe_lock_cafe_note
from .management_models import (
    FinancialSettings, FixedCost, Ingredient, IngredientPriceHistory,
    InventoryMovement, Recipe, RecipeIngredient,
)
from .management_services import sync_recipe_product_cost


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductPriceInline(admin.TabularInline):
    model = ProductPrice
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('unit_price', 'financial_line')

    @admin.display(description='Financeiro')
    def financial_line(self, obj):
        snap = getattr(obj, 'financial_snapshot', None)
        if not snap:
            return 'Custo ainda não cadastrado'
        if snap.cost_missing:
            return f'Faturamento R$ {snap.revenue:.2f} · custo pendente'
        return f'Custo R$ {snap.total_cost:.2f} · lucro R$ {snap.profit:.2f} · margem {snap.margin_percent:.2f}%'

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.order_type == 'cafe' and not cafe_order_editable(obj):
            fields.extend(['product', 'quantity', 'note'])
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.order_type == 'cafe' and not cafe_order_editable(obj):
            return False
        return super().has_delete_permission(request, obj)


class StatusInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('created_at',)


class EventQuoteItemInline(admin.TabularInline):
    model = EventQuoteItem
    extra = 1


class EventQuoteMessageInline(admin.TabularInline):
    model = EventQuoteMessage
    extra = 0
    readonly_fields = ('sender', 'body', 'created_at', 'read_at')
    fields = ('sender', 'body', 'created_at', 'read_at')
    can_delete = False


class EventQuoteStatusInline(admin.TabularInline):
    model = EventQuoteStatusHistory
    extra = 0
    readonly_fields = ('status', 'changed_by', 'note', 'created_at')
    can_delete = False


class CakeDesignInline(admin.StackedInline):
    model = CakeDesign
    extra = 0
    max_num = 1
    readonly_fields = ('selection_snapshot', 'created_at', 'updated_at')


class RecurringOrderItemInline(admin.TabularInline):
    model = RecurringOrderItem
    extra = 1


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ('ingredient',)


@admin.register(Category, site=secure_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'sort_order')
    list_editable = ('active', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Product, site=secure_admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'active', 'featured', 'sell_retail', 'sell_cafe', 'sell_event', 'lead_time_days', 'stock_limit')
    list_filter = ('category', 'active', 'featured', 'sell_retail', 'sell_cafe', 'sell_event')
    list_editable = ('active', 'featured')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = (ProductImageInline, ProductPriceInline,)


@admin.register(ProductCostProfile, site=secure_admin_site)
class ProductCostProfileAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'sale_unit', 'yield_quantity', 'production_cost', 'unit_cost', 'active', 'updated_at')
    list_filter = ('sale_unit', 'active')
    list_editable = ('active',)
    search_fields = ('sku', 'product__name', 'source_reference')
    autocomplete_fields = ('product',)
    readonly_fields = ('unit_cost', 'created_at', 'updated_at')
    fieldsets = (
        ('Produto', {'fields': ('product', 'sku', 'sale_unit', 'active')}),
        ('Custo de produção', {'fields': ('yield_quantity', 'production_cost', 'unit_cost', 'source_reference')}),
        ('Auditoria', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Ingredient, site=secure_admin_site)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'package_price', 'package_quantity', 'base_unit', 'unit_cost', 'stock', 'minimum_stock', 'active', 'supplier')
    list_filter = ('category', 'base_unit', 'active')
    list_editable = ('active',)
    search_fields = ('code', 'name', 'aliases', 'supplier')
    readonly_fields = ('unit_cost', 'created_at', 'updated_at')

    @admin.display(description='Estoque')
    def stock(self, obj):
        return obj.stock_balance


@admin.register(IngredientPriceHistory, site=secure_admin_site)
class IngredientPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'effective_date', 'package_price', 'package_quantity', 'unit_cost', 'supplier', 'source')
    list_filter = ('effective_date', 'ingredient__category')
    search_fields = ('ingredient__code', 'ingredient__name', 'supplier', 'source')
    readonly_fields = tuple(field.name for field in IngredientPriceHistory._meta.fields)
    date_hierarchy = 'effective_date'

    def has_add_permission(self, request):
        return False


@admin.register(InventoryMovement, site=secure_admin_site)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'ingredient', 'movement_type', 'quantity_delta', 'unit_cost_snapshot', 'reference', 'created_by')
    list_filter = ('movement_type', 'date', 'ingredient__category')
    search_fields = ('ingredient__code', 'ingredient__name', 'reference', 'notes')
    date_hierarchy = 'date'

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Recipe, site=secure_admin_site)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'sale_unit', 'yield_quantity', 'cost_total', 'cost_unit', 'product', 'active')
    list_filter = ('category', 'sale_unit', 'active')
    list_editable = ('active',)
    search_fields = ('code', 'name', 'source_reference')
    autocomplete_fields = ('product',)
    inlines = (RecipeIngredientInline,)

    @admin.display(description='Custo total')
    def cost_total(self, obj):
        return obj.production_cost

    @admin.display(description='Custo unitário')
    def cost_unit(self, obj):
        return obj.unit_cost

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_recipe_product_cost(obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sync_recipe_product_cost(form.instance)


@admin.register(FinancialSettings, site=secure_admin_site)
class FinancialSettingsAdmin(admin.ModelAdmin):
    list_display = ('desired_margin_percent', 'payment_fee_percent', 'tax_percent', 'contingency_percent', 'updated_at')

    def has_add_permission(self, request):
        return not FinancialSettings.objects.exists()


@admin.register(FixedCost, site=secure_admin_site)
class FixedCostAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'monthly_amount', 'due_day', 'active', 'start_date', 'end_date')
    list_filter = ('category', 'active')
    list_editable = ('active',)
    search_fields = ('name', 'notes')


@admin.register(PriceTable, site=secure_admin_site)
class PriceTableAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'active')
    list_filter = ('kind', 'active')
    filter_horizontal = ('assigned_users',)


@admin.register(CafeAccount, site=secure_admin_site)
class CafeAccountAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'approved', 'active', 'minimum_order', 'price_table')
    list_filter = ('approved', 'active')
    list_editable = ('approved', 'active')
    search_fields = ('business_name', 'user__email', 'contact_name')
    raw_id_fields = ('user',)


@admin.register(CustomerAddress, site=secure_admin_site)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'zip_code', 'street', 'city', 'default')
    search_fields = ('user__email', 'street', 'zip_code')
    list_filter = ('default', 'city')


@admin.register(DeliveryRegion, site=secure_admin_site)
class DeliveryRegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'delivery_fee', 'minimum_order')
    list_editable = ('active', 'delivery_fee', 'minimum_order')
    search_fields = ('name', 'zip_prefixes')


@admin.register(DeliveryRoute, site=secure_admin_site)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'weekdays', 'default_capacity', 'start_time', 'end_time')
    list_editable = ('active', 'default_capacity')
    filter_horizontal = ('regions',)


@admin.register(AvailabilityDay, site=secure_admin_site)
class AvailabilityDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'enabled', 'capacity', 'note')
    list_editable = ('enabled', 'capacity')
    date_hierarchy = 'date'


@admin.register(Order, site=secure_admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'customer', 'order_type', 'status', 'delivery_date', 'total', 'note_state', 'created_at')
    list_filter = ('status', 'order_type', 'delivery_date', 'delivery_region')
    search_fields = ('public_id', 'customer__username', 'customer__email', 'customer__first_name')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    inlines = (OrderItemInline, StatusInline,)
    date_hierarchy = 'created_at'

    def short_id(self, obj):
        return str(obj.public_id)[:8]
    short_id.short_description = 'Pedido'

    @admin.display(description='Nota')
    def note_state(self, obj):
        if obj.order_type != 'cafe':
            return '—'
        note = getattr(obj, 'cafe_delivery_note', None)
        if not note:
            return 'Aguardando nota'
        note = maybe_lock_cafe_note(note)
        return 'Fechada' if note.is_locked else f'Editável até {note.editable_until:%d/%m %H:%M}'

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.order_type == 'cafe' and not cafe_order_editable(obj):
            fields.extend([
                'customer', 'order_type', 'delivery_date', 'delivery_region', 'delivery_address',
                'delivery_fee', 'subtotal', 'discount', 'total', 'promotion_code', 'customer_note',
            ])
        return tuple(dict.fromkeys(fields))

    def save_model(self, request, obj, form, change):
        old_status = Order.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if old_status and old_status != obj.status:
            OrderStatusHistory.objects.create(order=obj, status=obj.status, changed_by=request.user, note='Status atualizado pela central administrativa.')


@admin.register(CafeDeliveryNote, site=secure_admin_site)
class CafeDeliveryNoteAdmin(admin.ModelAdmin):
    list_display = ('note_number', 'cafe_name', 'delivery_date', 'status', 'editable_until', 'quantity_snapshot', 'revenue_snapshot', 'profit_snapshot', 'payment_snapshot')
    list_filter = ('status', 'order__delivery_date', 'payment_snapshot')
    search_fields = ('note_number', 'order__public_id', 'order__customer__email', 'order__customer__cafe_account__business_name')
    readonly_fields = (
        'note_number', 'order', 'editable_until', 'locked_at', 'locked_by',
        'quantity_snapshot', 'revenue_snapshot', 'cost_snapshot', 'profit_snapshot',
        'margin_snapshot', 'payment_snapshot', 'created_at', 'updated_at',
    )
    actions = ('lock_selected_notes',)
    date_hierarchy = 'order__delivery_date'

    @admin.display(description='Cafeteria')
    def cafe_name(self, obj):
        cafe = getattr(obj.order.customer, 'cafe_account', None)
        return cafe.business_name if cafe else obj.order.customer.get_full_name() or obj.order.customer.username

    @admin.display(description='Entrega')
    def delivery_date(self, obj):
        return obj.order.delivery_date

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            maybe_lock_cafe_note(obj)
            if obj.is_locked:
                fields.extend(['status', 'note'])
        return tuple(dict.fromkeys(fields))

    @admin.action(description='Fechar notas selecionadas agora')
    def lock_selected_notes(self, request, queryset):
        count = 0
        for note in queryset:
            if not note.locked_at and note.status == 'draft':
                lock_cafe_note(note, user=request.user, force=True)
                count += 1
        self.message_user(request, f'{count} nota(s) fechada(s).')


@admin.register(OrderItemFinancialSnapshot, site=secure_admin_site)
class OrderItemFinancialSnapshotAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product_name', 'quantity', 'unit_price', 'unit_cost', 'revenue', 'total_cost', 'profit', 'margin_percent', 'cost_missing')
    list_filter = ('cost_missing', 'order_item__order__order_type', 'order_item__order__delivery_date')
    search_fields = ('sku', 'product_name', 'order_item__order__public_id')
    readonly_fields = tuple(field.name for field in OrderItemFinancialSnapshot._meta.fields)
    date_hierarchy = 'order_item__order__delivery_date'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BusinessExpense, site=secure_admin_site)
class BusinessExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'category', 'supplier', 'amount', 'payment_status', 'payment_method')
    list_filter = ('category', 'payment_status', 'date')
    list_editable = ('payment_status',)
    search_fields = ('description', 'supplier', 'notes')
    date_hierarchy = 'date'

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment, site=secure_admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'provider', 'provider_id', 'status', 'amount', 'method', 'created_at')
    list_filter = ('status', 'provider', 'method')
    readonly_fields = ('order', 'provider', 'provider_id', 'status', 'amount', 'method', 'paid_at', 'raw_reference', 'created_at', 'updated_at')


@admin.register(CustomerProfile, site=secure_admin_site)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'customer_type', 'phone', 'orders_count', 'lifetime_value', 'marketing_opt_in')
    list_filter = ('customer_type', 'marketing_opt_in')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('orders_count', 'lifetime_value')


@admin.register(Promotion, site=secure_admin_site)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'audience', 'percent_off', 'minimum_orders', 'minimum_spend', 'max_uses_per_user', 'active', 'starts_at', 'ends_at')
    list_filter = ('audience', 'active')
    search_fields = ('name', 'code')


@admin.register(PromotionRedemption, site=secure_admin_site)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'user', 'order', 'discount_amount', 'created_at')
    readonly_fields = ('promotion', 'user', 'order', 'discount_amount', 'created_at', 'updated_at')


@admin.register(EventQuote, site=secure_admin_site)
class EventQuoteAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'customer', 'event_type', 'event_date', 'guest_count', 'status', 'estimated_total', 'final_total')
    list_filter = ('status', 'event_type', 'event_date')
    search_fields = ('public_id', 'customer__email', 'customer__first_name')
    readonly_fields = ('public_id', 'converted_order', 'created_at', 'updated_at')
    inlines = (CakeDesignInline, EventQuoteItemInline, EventQuoteStatusInline, EventQuoteMessageInline)

    def short_id(self, obj):
        return str(obj.public_id)[:8]


@admin.register(RecurringOrder, site=secure_admin_site)
class RecurringOrderAdmin(admin.ModelAdmin):
    list_display = ('name', 'cafe', 'weekday', 'active', 'delivery_region')
    list_filter = ('active', 'weekday', 'delivery_region')
    inlines = (RecurringOrderItemInline,)


@admin.register(Conversation, site=secure_admin_site)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('order', 'customer', 'closed', 'updated_at')
    list_filter = ('closed',)
    search_fields = ('customer__username', 'order__public_id')


@admin.register(Message, site=secure_admin_site)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'created_at', 'read_at')
    search_fields = ('body', 'sender__username')
    readonly_fields = ('body', 'sender', 'conversation', 'created_at', 'read_at')


@admin.register(Favorite, site=secure_admin_site)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'user__email', 'product__name')
    readonly_fields = ('user', 'product', 'created_at', 'updated_at')


@admin.register(CakeOption, site=secure_admin_site)
class CakeOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'preview_color', 'active', 'sort_order')
    list_filter = ('kind', 'active')
    list_editable = ('active', 'sort_order')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
