from django.contrib import admin
from .models import *

admin.site.site_header='Nossas Delícias — Central Administrativa'
admin.site.site_title='Nossas Delícias'
admin.site.index_title='Operação, catálogo e clientes'

class ProductImageInline(admin.TabularInline): model=ProductImage; extra=1
class ProductPriceInline(admin.TabularInline): model=ProductPrice; extra=1
class OrderItemInline(admin.TabularInline): model=OrderItem; extra=0; readonly_fields=('unit_price',)
class StatusInline(admin.TabularInline): model=OrderStatusHistory; extra=0; readonly_fields=('created_at',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display=('name','active','sort_order'); list_editable=('active','sort_order'); prepopulated_fields={'slug':('name',)}; search_fields=('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display=('name','category','active','featured','lead_time_days','stock_limit'); list_filter=('category','active','featured'); list_editable=('active','featured'); search_fields=('name','description'); prepopulated_fields={'slug':('name',)}; inlines=(ProductImageInline,ProductPriceInline,)

@admin.register(PriceTable)
class PriceTableAdmin(admin.ModelAdmin): list_display=('name','kind','active'); filter_horizontal=('assigned_users',)

@admin.register(DeliveryRegion)
class DeliveryRegionAdmin(admin.ModelAdmin): list_display=('name','active','delivery_fee','minimum_order'); list_editable=('active','delivery_fee','minimum_order'); search_fields=('name','zip_prefixes')

@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin): list_display=('name','active','weekdays','default_capacity','start_time','end_time'); list_editable=('active','default_capacity'); filter_horizontal=('regions',)

@admin.register(AvailabilityDay)
class AvailabilityDayAdmin(admin.ModelAdmin): list_display=('date','enabled','capacity','note'); list_editable=('enabled','capacity'); date_hierarchy='date'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display=('public_id','customer','order_type','status','delivery_date','total','created_at'); list_filter=('status','order_type','delivery_date','delivery_region'); search_fields=('public_id','customer__username','customer__email','customer__first_name'); readonly_fields=('public_id','created_at','updated_at'); inlines=(OrderItemInline,StatusInline,)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin): list_display=('order','provider','provider_id','status','amount','method','created_at'); list_filter=('status','provider','method'); readonly_fields=('raw_reference',)

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin): list_display=('user','customer_type','phone','orders_count','lifetime_value','marketing_opt_in'); list_filter=('customer_type','marketing_opt_in'); search_fields=('user__username','user__email','phone')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin): list_display=('name','code','audience','percent_off','minimum_orders','active','starts_at','ends_at'); list_filter=('audience','active')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin): list_display=('order','customer','closed','updated_at'); list_filter=('closed',); search_fields=('customer__username','order__public_id')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin): list_display=('conversation','sender','created_at','read_at'); search_fields=('body','sender__username'); readonly_fields=('body','sender','conversation','created_at','read_at')
