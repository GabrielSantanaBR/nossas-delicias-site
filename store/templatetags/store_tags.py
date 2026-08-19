from django import template
from store.models import ProductPrice
from store.services import price_for

register=template.Library()

@register.simple_tag(takes_context=True)
def product_price(context,product,quantity=1):
    user=context.get('user')
    if user and user.is_authenticated:
        value=price_for(user,product,quantity)
    else:
        row=ProductPrice.objects.filter(product=product,table__kind='retail',table__active=True,min_quantity__lte=quantity).order_by('-min_quantity').first()
        value=row.unit_price if row else None
    return value

@register.simple_tag(takes_context=True)
def cart_count(context):
    user=context.get('user')
    if not user or not user.is_authenticated: return 0
    try: return sum(item.quantity for item in user.cart.items.all())
    except Exception: return 0
