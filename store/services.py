from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AvailabilityDay,
    Cart,
    DeliveryRegion,
    DeliveryRoute,
    Order,
    PriceTable,
    ProductPrice,
    Promotion,
)

CENT = Decimal('0.01')
SLOT_HOLD_MINUTES = 45
ACTIVE_FULFILLMENT_STATUSES = {'paid', 'production', 'ready', 'delivery', 'completed'}
RETAIL_MIN_LEAD_DAYS = 7
RETAIL_DAILY_CAPACITY = 5


def money(value):
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def customer_order_type(user):
    """Return the commercial channel the user is actually authorized to use.

    A cafeteria application must never unlock B2B pricing by itself. The cafe
    channel is granted only when CafeAccount is both approved and active.
    """
    cafe = getattr(user, 'cafe_account', None)
    if cafe:
        if cafe.approved and cafe.active:
            return 'cafe'
        return 'retail'
    profile = getattr(user, 'customer_profile', None)
    if profile and profile.customer_type in {'retail', 'event'}:
        return profile.customer_type
    return 'retail'


def price_for(user, product, quantity=1, order_type=None):
    quantity = max(int(quantity or 1), 1)
    order_type = order_type or customer_order_type(user)

    assigned = PriceTable.objects.filter(active=True, assigned_users=user)
    price = ProductPrice.objects.filter(
        product=product,
        table__in=assigned,
        min_quantity__lte=quantity,
    ).order_by('-min_quantity', '-updated_at').first()
    if price:
        return price.unit_price

    cafe = getattr(user, 'cafe_account', None)
    if order_type == 'cafe':
        if not cafe or not cafe.approved or not cafe.active:
            order_type = 'retail'
        elif cafe.price_table_id:
            price = ProductPrice.objects.filter(
                product=product,
                table=cafe.price_table,
                table__active=True,
                min_quantity__lte=quantity,
            ).order_by('-min_quantity', '-updated_at').first()
            if price:
                return price.unit_price

    price = ProductPrice.objects.filter(
        product=product,
        table__kind=order_type,
        table__active=True,
        min_quantity__lte=quantity,
    ).order_by('-min_quantity', '-updated_at').first()
    if not price and order_type != 'retail':
        price = ProductPrice.objects.filter(
            product=product,
            table__kind='retail',
            table__active=True,
            min_quantity__lte=quantity,
        ).order_by('-min_quantity', '-updated_at').first()
    return price.unit_price if price else None


def product_allowed(product, order_type):
    return {
        'retail': product.sell_retail,
        'cafe': product.sell_cafe,
        'event': product.sell_event,
    }.get(order_type, False)


def cart_snapshot(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    order_type = customer_order_type(user)
    rows = []
    subtotal = Decimal('0.00')
    max_lead = 1

    for item in cart.items.select_related('product', 'product__category').all():
        product = item.product
        if not product.active or not product_allowed(product, order_type):
            continue
        quantity = max(item.quantity, product.min_quantity)
        unit_price = price_for(user, product, quantity, order_type)
        if unit_price is None:
            continue
        total = money(Decimal(unit_price) * quantity)
        subtotal += total
        max_lead = max(max_lead, product.lead_time_days)
        rows.append({
            'item': item,
            'product': product,
            'quantity': quantity,
            'unit_price': unit_price,
            'total': total,
        })

    return {
        'cart': cart,
        'rows': rows,
        'subtotal': money(subtotal),
        'max_lead': effective_lead_days(order_type, max_lead),
        'order_type': order_type,
    }


def region_for_zip(zip_code):
    for region in DeliveryRegion.objects.filter(active=True).order_by('id'):
        if region.matches_zip(zip_code):
            return region
    return None


def _route_channel(route):
    """Use an explicit route-name convention without changing the DB schema.

    Routes beginning with `Clientes |` are retail-only and routes beginning
    with `Cafeterias |` are B2B-only. Existing unprefixed routes remain shared
    for backwards compatibility.
    """
    normalized = (route.name or '').strip().lower()
    if normalized.startswith('clientes |'):
        return 'retail'
    if normalized.startswith('cafeterias |'):
        return 'cafe'
    return 'all'


def effective_lead_days(order_type, lead_days=1):
    requested = max(int(lead_days or 1), 1)
    if order_type == 'retail':
        return max(RETAIL_MIN_LEAD_DAYS, requested)
    return requested


def route_for(region, date, order_type=None, lock=False):
    queryset = DeliveryRoute.objects.filter(active=True, regions=region).distinct()
    if lock:
        queryset = queryset.select_for_update()
    for route in queryset:
        channel = _route_channel(route)
        if date.weekday() not in route.weekday_set():
            continue
        if order_type and channel not in {'all', order_type}:
            continue
        return route
    return None


def capacity_for(region, date, order_type=None):
    route = route_for(region, date, order_type=order_type)
    if not route:
        return 0
    override = AvailabilityDay.objects.filter(date=date).first()
    if override and not override.enabled:
        return 0
    return override.capacity if override else route.default_capacity


def scheduled_orders(region, date, order_type=None):
    hold_threshold = timezone.now() - timedelta(minutes=SLOT_HOLD_MINUTES)
    active = Q(status__in=ACTIVE_FULFILLMENT_STATUSES)
    fresh_pending = Q(status='pending_payment', created_at__gte=hold_threshold)
    queryset = Order.objects.filter(
        delivery_region=region,
        delivery_date=date,
    ).filter(active | fresh_pending)
    if order_type:
        queryset = queryset.filter(order_type=order_type)
    return queryset


def scheduled_count(region, date, order_type=None):
    return scheduled_orders(region, date, order_type=order_type).count()


def retail_scheduled_count(date):
    hold_threshold = timezone.now() - timedelta(minutes=SLOT_HOLD_MINUTES)
    active = Q(status__in=ACTIVE_FULFILLMENT_STATUSES)
    fresh_pending = Q(status='pending_payment', created_at__gte=hold_threshold)
    return Order.objects.filter(order_type='retail', delivery_date=date).filter(active | fresh_pending).count()


def can_schedule(region, date, lead_days=1, order_type='retail'):
    today = timezone.localdate()
    lead = effective_lead_days(order_type, lead_days)
    if date < today + timedelta(days=lead):
        return False
    capacity = capacity_for(region, date, order_type=order_type)
    if capacity <= 0 or scheduled_count(region, date, order_type=order_type) >= capacity:
        return False
    if order_type == 'retail' and retail_scheduled_count(date) >= RETAIL_DAILY_CAPACITY:
        return False
    return True


def lock_delivery_slot(region, date, lead_days=1, order_type='retail'):
    """Serialize the last capacity check inside an atomic checkout."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('lock_delivery_slot precisa ser executado dentro de transaction.atomic().')
    lead = effective_lead_days(order_type, lead_days)
    if date < timezone.localdate() + timedelta(days=lead):
        return False

    # Retail has a global five-orders-per-day ceiling. Locking all route rows
    # makes concurrent checkouts serialize even when Nilópolis and Zona Oeste
    # are represented by different regions on the same route.
    if order_type == 'retail':
        list(DeliveryRoute.objects.select_for_update().filter(active=True).order_by('pk'))

    route = route_for(region, date, order_type=order_type, lock=True)
    if not route:
        return False
    override = AvailabilityDay.objects.select_for_update().filter(date=date).first()
    if override and not override.enabled:
        return False
    capacity = override.capacity if override else route.default_capacity
    if capacity <= 0 or scheduled_count(region, date, order_type=order_type) >= capacity:
        return False
    if order_type == 'retail' and retail_scheduled_count(date) >= RETAIL_DAILY_CAPACITY:
        return False
    return True


def available_dates(region, lead_days=1, horizon_days=45, limit=12, order_type='retail'):
    lead = effective_lead_days(order_type, lead_days)
    start = timezone.localdate() + timedelta(days=lead)
    results = []
    for offset in range(max(int(horizon_days or 0), 0) + 1):
        date = start + timedelta(days=offset)
        capacity = capacity_for(region, date, order_type=order_type)
        used = scheduled_count(region, date, order_type=order_type) if capacity else 0
        remaining = max(capacity - used, 0)
        if order_type == 'retail':
            remaining = min(remaining, max(RETAIL_DAILY_CAPACITY - retail_scheduled_count(date), 0))
        if capacity and remaining > 0:
            route = route_for(region, date, order_type=order_type)
            results.append({
                'date': date,
                'remaining': remaining,
                'start_time': route.start_time,
                'end_time': route.end_time,
            })
            if len(results) >= limit:
                break
    return results


def eligible_promotions(user):
    now = timezone.now()
    profile = getattr(user, 'customer_profile', None)
    queryset = Promotion.objects.filter(active=True, starts_at__lte=now, ends_at__gte=now)
    if not profile:
        return list(queryset.filter(audience='all'))

    audiences = ['all', customer_order_type(user)]
    if profile.orders_count >= 2:
        audiences.append('loyal')
    queryset = queryset.filter(
        audience__in=audiences,
        minimum_orders__lte=profile.orders_count,
        minimum_spend__lte=profile.lifetime_value,
    )

    redemption_counts = {}
    for promotion_id in user.promotion_redemptions.values_list('promotion_id', flat=True):
        redemption_counts[promotion_id] = redemption_counts.get(promotion_id, 0) + 1
    return [
        promotion for promotion in queryset
        if redemption_counts.get(promotion.id, 0) < promotion.max_uses_per_user
    ]


def promotion_for_code(user, code):
    normalized = (code or '').strip().upper()
    if not normalized:
        return None
    for promotion in eligible_promotions(user):
        if promotion.code.upper() == normalized:
            return promotion
    return None


def discount_for(promotion, subtotal):
    if not promotion:
        return Decimal('0.00')
    subtotal = money(subtotal)
    discount = subtotal * (promotion.percent_off / Decimal('100'))
    return min(money(discount), subtotal)
