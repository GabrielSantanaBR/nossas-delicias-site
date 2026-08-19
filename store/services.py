from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from django.utils import timezone
from .models import AvailabilityDay, Cart, DeliveryRegion, DeliveryRoute, Order, PriceTable, ProductPrice, Promotion


def customer_order_type(user):
    cafe=getattr(user,'cafe_account',None)
    if cafe and cafe.approved and cafe.active:
        return 'cafe'
    profile=getattr(user,'customer_profile',None)
    return profile.customer_type if profile and profile.customer_type in {'retail','cafe','event'} else 'retail'


def price_for(user,product,quantity=1,order_type=None):
    order_type=order_type or customer_order_type(user)
    assigned=PriceTable.objects.filter(active=True,assigned_users=user)
    price=ProductPrice.objects.filter(product=product,table__in=assigned,min_quantity__lte=quantity).order_by('-min_quantity').first()
    if price: return price.unit_price
    cafe=getattr(user,'cafe_account',None)
    if order_type=='cafe' and cafe and cafe.approved and cafe.price_table_id:
        price=ProductPrice.objects.filter(product=product,table=cafe.price_table,table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
        if price: return price.unit_price
    price=ProductPrice.objects.filter(product=product,table__kind=order_type,table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
    if not price:
        price=ProductPrice.objects.filter(product=product,table__kind='retail',table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
    return price.unit_price if price else None


def product_allowed(product,order_type):
    return {'retail':product.sell_retail,'cafe':product.sell_cafe,'event':product.sell_event}.get(order_type,False)


def cart_snapshot(user):
    cart,_=Cart.objects.get_or_create(user=user)
    order_type=customer_order_type(user)
    rows=[]; subtotal=Decimal('0.00'); max_lead=1
    for item in cart.items.select_related('product','product__category').all():
        if not item.product.active or not product_allowed(item.product,order_type): continue
        qty=max(item.quantity,item.product.min_quantity)
        unit=price_for(user,item.product,qty,order_type)
        if unit is None: continue
        total=(unit*qty).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        subtotal+=total; max_lead=max(max_lead,item.product.lead_time_days)
        rows.append({'item':item,'product':item.product,'quantity':qty,'unit_price':unit,'total':total})
    return {'cart':cart,'rows':rows,'subtotal':subtotal,'max_lead':max_lead,'order_type':order_type}


def region_for_zip(zip_code):
    for region in DeliveryRegion.objects.filter(active=True):
        if region.matches_zip(zip_code): return region
    return None


def _route_for(region,date):
    for route in DeliveryRoute.objects.filter(active=True,regions=region):
        if date.weekday() in route.weekday_set(): return route
    return None


def capacity_for(region,date):
    route=_route_for(region,date)
    if not route: return 0
    override=AvailabilityDay.objects.filter(date=date).first()
    if override and not override.enabled: return 0
    return override.capacity if override else route.default_capacity


def scheduled_count(region,date):
    return Order.objects.filter(delivery_region=region,delivery_date=date).exclude(status='cancelled').count()


def can_schedule(region,date,lead_days=1):
    today=timezone.localdate()
    if date < today+timedelta(days=lead_days): return False
    capacity=capacity_for(region,date)
    return capacity>0 and scheduled_count(region,date)<capacity


def available_dates(region,lead_days=1,horizon_days=45,limit=12):
    start=timezone.localdate()+timedelta(days=lead_days)
    results=[]
    for offset in range(horizon_days+1):
        date=start+timedelta(days=offset)
        capacity=capacity_for(region,date)
        used=scheduled_count(region,date) if capacity else 0
        if capacity and used<capacity:
            route=_route_for(region,date)
            results.append({'date':date,'remaining':capacity-used,'start_time':route.start_time,'end_time':route.end_time})
            if len(results)>=limit: break
    return results


def eligible_promotions(user):
    now=timezone.now(); profile=getattr(user,'customer_profile',None)
    qs=Promotion.objects.filter(active=True,starts_at__lte=now,ends_at__gte=now)
    if not profile: return qs.filter(audience='all')
    audiences=['all',customer_order_type(user)]
    if profile.orders_count>=2: audiences.append('loyal')
    qs=qs.filter(audience__in=audiences,minimum_orders__lte=profile.orders_count,minimum_spend__lte=profile.lifetime_value)
    return [p for p in qs if user.promotion_redemptions.filter(promotion=p).count()<p.max_uses_per_user]


def promotion_for_code(user,code):
    code=(code or '').strip().upper()
    for promotion in eligible_promotions(user):
        if promotion.code.upper()==code: return promotion
    return None


def discount_for(promotion,subtotal):
    if not promotion: return Decimal('0.00')
    return (subtotal*(promotion.percent_off/Decimal('100'))).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
