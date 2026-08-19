import hashlib
import hmac
import json
from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import DeliveryRegion, PriceTable, ProductPrice, Promotion

def price_for(user, product, quantity=1, order_type='retail'):
    tables=PriceTable.objects.filter(active=True).filter(Q(assigned_users=user)|Q(kind=order_type)).distinct()
    price=(ProductPrice.objects.filter(product=product,table__in=tables,min_quantity__lte=quantity).order_by('-min_quantity').first())
    if not price:
        price=ProductPrice.objects.filter(product=product,table__kind='retail',table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
    return price.unit_price if price else None

def region_for_zip(zip_code):
    for region in DeliveryRegion.objects.filter(active=True):
        if region.matches_zip(zip_code): return region
    return None

def eligible_promotions(user):
    now=timezone.now(); profile=getattr(user,'customer_profile',None)
    qs=Promotion.objects.filter(active=True,starts_at__lte=now,ends_at__gte=now)
    if not profile: return qs.filter(audience='all')
    audiences=['all',profile.customer_type]
    if profile.orders_count>=2: audiences.append('loyal')
    return qs.filter(audience__in=audiences,minimum_orders__lte=profile.orders_count,minimum_spend__lte=profile.lifetime_value)

def verify_mp_signature(raw_body: bytes, signature: str) -> bool:
    secret=settings.MERCADO_PAGO_WEBHOOK_SECRET.encode()
    if not secret or not signature: return False
    # Adapter intentionally conservative: production integration should use the exact
    # Mercado Pago signature manifest fields returned with each webhook event.
    digest=hmac.new(secret,raw_body,hashlib.sha256).hexdigest()
    supplied=signature.split('v1=')[-1].split(',')[0].strip()
    return hmac.compare_digest(digest,supplied)

def safe_payment_reference(payload):
    data=payload.get('data') or {}
    return {'event_type':payload.get('type') or payload.get('action'),'provider_object_id':str(data.get('id',''))[:160]}
