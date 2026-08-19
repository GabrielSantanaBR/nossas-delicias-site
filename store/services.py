from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from .models import AvailabilityDay, DeliveryRegion, DeliveryRoute, Order, PriceTable, ProductPrice, Promotion


def price_for(user, product, quantity=1, order_type='retail'):
    tables=PriceTable.objects.filter(active=True).filter(Q(assigned_users=user)|Q(kind=order_type)).distinct()
    price=ProductPrice.objects.filter(product=product,table__in=tables,min_quantity__lte=quantity).order_by('-min_quantity').first()
    if not price:
        price=ProductPrice.objects.filter(product=product,table__kind='retail',table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
    return price.unit_price if price else None


def region_for_zip(zip_code):
    for region in DeliveryRegion.objects.filter(active=True):
        if region.matches_zip(zip_code): return region
    return None


def _route_for(region, date):
    for route in DeliveryRoute.objects.filter(active=True,regions=region):
        if date.weekday() in route.weekday_set(): return route
    return None


def capacity_for(region, date):
    route=_route_for(region,date)
    if not route: return 0
    override=AvailabilityDay.objects.filter(date=date).first()
    if override and not override.enabled: return 0
    return override.capacity if override else route.default_capacity


def scheduled_count(region, date):
    return Order.objects.filter(delivery_region=region,delivery_date=date).exclude(status='cancelled').count()


def can_schedule(region, date, lead_days=1):
    today=timezone.localdate()
    if date < today + timedelta(days=lead_days): return False
    capacity=capacity_for(region,date)
    return capacity > 0 and scheduled_count(region,date) < capacity


def available_dates(region, lead_days=1, horizon_days=45, limit=12):
    start=timezone.localdate()+timedelta(days=lead_days)
    results=[]
    for offset in range(horizon_days+1):
        date=start+timedelta(days=offset)
        capacity=capacity_for(region,date)
        used=scheduled_count(region,date) if capacity else 0
        if capacity and used < capacity:
            route=_route_for(region,date)
            results.append({'date':date,'remaining':capacity-used,'start_time':route.start_time,'end_time':route.end_time})
            if len(results)>=limit: break
    return results


def eligible_promotions(user):
    now=timezone.now(); profile=getattr(user,'customer_profile',None)
    qs=Promotion.objects.filter(active=True,starts_at__lte=now,ends_at__gte=now)
    if not profile: return qs.filter(audience='all')
    audiences=['all',profile.customer_type]
    if profile.orders_count>=2: audiences.append('loyal')
    return qs.filter(audience__in=audiences,minimum_orders__lte=profile.orders_count,minimum_spend__lte=profile.lifetime_value)
