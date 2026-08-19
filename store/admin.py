from django.contrib import admin
from .admin_site import secure_admin_site
from .models import *

class ProductImageInline(admin.TabularInline): model=ProductImage; extra=1
class ProductPriceInline(admin.TabularInline): model=ProductPrice; extra=1
class OrderItemInline(admin.TabularInline): model=OrderItem; extra=0; readonly_fields=('unit_price',)
class StatusInline(admin.TabularInline): model=OrderStatusHistory; extra=0; readonly_fields=('created_at',)
class EventQuoteItemInline(admin.TabularInline): model=EventQuoteItem; extra=1
class RecurringOrderItemInline(admin.TabularInline): model=RecurringOrderItem; extra=1

@admin.register(Category,site=secure_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display=('name','active','sort_order'); list_editable=('active','sort_order'); prepopulated_fields={'slug':('name',)}; search_fields=('name',)

@admin.register(Product,site=secure_admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display=('name','category','active','featured','sell_retail','sell_cafe','sell_event','lead_time_days','stock_limit'); list_filter=('category','active','featured','sell_retail','sell_cafe','sell_event'); list_editable=('active','featured'); search_fields=('name','description'); prepopulated_fields={'slug':('name',)}; inlines=(ProductImageInline,ProductPriceInline,)

@admin.register(PriceTable,site=secure_admin_site)
class PriceTableAdmin(admin.ModelAdmin): list_display=('name','kind','active'); list_filter=('kind','active'); filter_horizontal=('assigned_users',)

@admin.register(CafeAccount,site=secure_admin_site)
class CafeAccountAdmin(admin.ModelAdmin):
    list_display=('business_name','user','approved','active','minimum_order','price_table'); list_filter=('approved','active'); list_editable=('approved','active'); search_fields=('business_name','user__email','contact_name'); raw_id_fields=('user',)

@admin.register(CustomerAddress,site=secure_admin_site)
class CustomerAddressAdmin(admin.ModelAdmin): list_display=('user','label','zip_code','street','city','default'); search_fields=('user__email','street','zip_code'); list_filter=('default','city')

@admin.register(DeliveryRegion,site=secure_admin_site)
class DeliveryRegionAdmin(admin.ModelAdmin): list_display=('name','active','delivery_fee','minimum_order'); list_editable=('active','delivery_fee','minimum_order'); search_fields=('name','zip_prefixes')

@admin.register(DeliveryRoute,site=secure_admin_site)
class DeliveryRouteAdmin(admin.ModelAdmin): list_display=('name','active','weekdays','default_capacity','start_time','end_time'); list_editable=('active','default_capacity'); filter_horizontal=('regions',)

@admin.register(AvailabilityDay,site=secure_admin_site)
class AvailabilityDayAdmin(admin.ModelAdmin): list_display=('date','enabled','capacity','note'); list_editable=('enabled','capacity'); date_hierarchy='date'

@admin.register(Order,site=secure_admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display=('short_id','customer','order_type','status','delivery_date','total','created_at'); list_filter=('status','order_type','delivery_date','delivery_region'); search_fields=('public_id','customer__username','customer__email','customer__first_name'); readonly_fields=('public_id','created_at','updated_at'); inlines=(OrderItemInline,StatusInline,); date_hierarchy='created_at'
    def short_id(self,obj): return str(obj.public_id)[:8]
    short_id.short_description='Pedido'
    def save_model(self,request,obj,form,change):
        old_status=Order.objects.filter(pk=obj.pk).values_list('status',flat=True).first() if change else None
        super().save_model(request,obj,form,change)
        if old_status and old_status!=obj.status:
            OrderStatusHistory.objects.create(order=obj,status=obj.status,changed_by=request.user,note='Status atualizado pela central administrativa.')

@admin.register(Payment,site=secure_admin_site)
class PaymentAdmin(admin.ModelAdmin): list_display=('order','provider','provider_id','status','amount','method','created_at'); list_filter=('status','provider','method'); readonly_fields=('order','provider','provider_id','status','amount','method','paid_at','raw_reference','created_at','updated_at')

@admin.register(CustomerProfile,site=secure_admin_site)
class CustomerProfileAdmin(admin.ModelAdmin): list_display=('user','customer_type','phone','orders_count','lifetime_value','marketing_opt_in'); list_filter=('customer_type','marketing_opt_in'); search_fields=('user__username','user__email','phone'); readonly_fields=('orders_count','lifetime_value')

@admin.register(Promotion,site=secure_admin_site)
class PromotionAdmin(admin.ModelAdmin): list_display=('name','code','audience','percent_off','minimum_orders','minimum_spend','max_uses_per_user','active','starts_at','ends_at'); list_filter=('audience','active'); search_fields=('name','code')

@admin.register(PromotionRedemption,site=secure_admin_site)
class PromotionRedemptionAdmin(admin.ModelAdmin): list_display=('promotion','user','order','discount_amount','created_at'); readonly_fields=('promotion','user','order','discount_amount','created_at','updated_at')

@admin.register(EventQuote,site=secure_admin_site)
class EventQuoteAdmin(admin.ModelAdmin):
    list_display=('short_id','customer','event_type','event_date','guest_count','status','estimated_total','final_total'); list_filter=('status','event_type','event_date'); search_fields=('public_id','customer__email','customer__first_name'); readonly_fields=('public_id','converted_order','created_at','updated_at'); inlines=(EventQuoteItemInline,)
    def short_id(self,obj): return str(obj.public_id)[:8]

@admin.register(RecurringOrder,site=secure_admin_site)
class RecurringOrderAdmin(admin.ModelAdmin): list_display=('name','cafe','weekday','active','delivery_region'); list_filter=('active','weekday','delivery_region'); inlines=(RecurringOrderItemInline,)

@admin.register(Conversation,site=secure_admin_site)
class ConversationAdmin(admin.ModelAdmin): list_display=('order','customer','closed','updated_at'); list_filter=('closed',); search_fields=('customer__username','order__public_id')

@admin.register(Message,site=secure_admin_site)
class MessageAdmin(admin.ModelAdmin): list_display=('conversation','sender','created_at','read_at'); search_fields=('body','sender__username'); readonly_fields=('body','sender','conversation','created_at','read_at')
