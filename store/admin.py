from django.contrib import admin
from .admin_site import secure_admin_site
from .models import *

class ProductImageInline(admin.TabularInline): model=ProductImage; extra=1
class ProductPriceInline(admin.TabularInline): model=ProductPrice; extra=1
class OrderItemInline(admin.TabularInline): model=OrderItem; extra=0; readonly_fields=('unit_price',)
class StatusInline(admin.TabularInline): model=OrderStatusHistory; extra=0; readonly_fields=('created_at',)

@admin.register(Category,site=secure_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display=('name','active','sort_order'); list_editable=('active','sort_order'); prepopulated_fields={'slug':('name',)}; search_fields=('name',)

@admin.register(Product,site=secure_admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display=('name','category','active','featured','lead_time_days','stock_limit'); list_filter=('category','active','featured'); list_editable=('active','featured'); search_fields=('name','description'); prepopulated_fields={'slug':('name',)}; inlines=(ProductImageInline,ProductPriceInline,)

@admin.register(PriceTable,site=secure_admin_site)
class PriceTableAdmin(admin.ModelAdmin): list_display=('name','kind','active'); filter_horizontal=('assigned_users',)

@admin.register(DeliveryRegion,site=secure_admin_site)
class DeliveryRegionAdmin(admin.ModelAdmin): list_display=('name','active','delivery_fee','minimum_order'); list_editable=('active','delivery_fee','minimum_order'); search_fields=('name','zip_prefixes')

@admin.register(DeliveryRoute,site=secure_admin_site)
class DeliveryRouteAdmin(admin.ModelAdmin): list_display=('name','active','weekdays','default_capacity','start_time','end_time'); list_editable=('active','default_capacity'); filter_horizontal=('regions',)

@admin.register(AvailabilityDay,site=secure_admin_site)
class AvailabilityDayAdmin(admin.ModelAdmin): list_display=('date','enabled','capacity','note'); list_editable=('enabled','capacity'); date_hierarchy='date'

@admin.register(Order,site=secure_admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display=('public_id','customer','order_type','status','delivery_date','total','created_at'); list_filter=('status','order_type','delivery_date','delivery_region'); search_fields=('public_id','customer__username','customer__email','customer__first_name'); readonly_fields=('public_id','created_at','updated_at'); inlines=(OrderItemInline,StatusInline,)

@admin.register(Payment,site=secure_admin_site)
class PaymentAdmin(admin.ModelAdmin): list_display=('order','provider','provider_id','status','amount','method','created_at'); list_filter=('status','provider','method'); readonly_fields=('raw_reference',)

@admin.register(CustomerProfile,site=secure_admin_site)
class CustomerProfileAdmin(admin.ModelAdmin): list_display=('user','customer_type','phone','orders_count','lifetime_value','marketing_opt_in'); list_filter=('customer_type','marketing_opt_in'); search_fields=('user__username','user__email','phone')

@admin.register(Promotion,site=secure_admin_site)
class PromotionAdmin(admin.ModelAdmin): list_display=('name','code','audience','percent_off','minimum_orders','active','starts_at','ends_at'); list_filter=('audience','active')

@admin.register(Conversation,site=secure_admin_site)
class ConversationAdmin(admin.ModelAdmin): list_display=('order','customer','closed','updated_at'); list_filter=('closed',); search_fields=('customer__username','order__public_id')

@admin.register(Message,site=secure_admin_site)
class MessageAdmin(admin.ModelAdmin): list_display=('conversation','sender','created_at','read_at'); search_fields=('body','sender__username'); readonly_fields=('body','sender','conversation','created_at','read_at')
