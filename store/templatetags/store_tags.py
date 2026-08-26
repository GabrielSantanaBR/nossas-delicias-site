from django import template
from django.templatetags.static import static
from store.models import ProductPrice
from store.services import price_for
from store.financial_services import cafe_order_editable, ensure_cafe_note, maybe_lock_cafe_note

register=template.Library()


def _product_fallback_filename(product):
    slug = getattr(product, 'slug', '') or ''
    category = getattr(getattr(product, 'category', None), 'slug', '') or ''
    if slug == 'bolo-personalizado-monte-o-seu':
        filename = 'bolo-personalizado.webp'
    elif 'brigadeiro' in slug or 'brigadeiro' in category:
        filename = 'brigadeiros-gourmet.webp'
    elif 'banoffee' in slug or 'torta' in category:
        filename = 'banoffee-brownies.webp'
    elif 'brownie' in slug or 'brownie' in category:
        filename = 'confeitaria-hero.webp'
    else:
        filename = 'confeitaria-hero.webp'
    return filename


@register.simple_tag
def product_fallback_visual(product):
    return static(f'images/showcase/{_product_fallback_filename(product)}')


@register.simple_tag
def product_visual(product):
    """Return an uploaded image when available and a local, reliable showcase otherwise."""
    if product and product.image:
        try:
            return product.image.url
        except (ValueError, AttributeError):
            pass
    return product_fallback_visual(product)


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
    if not user or not user.is_authenticated:
        return 0
    try:
        return sum(item.quantity for item in user.cart.items.all())
    except Exception:
        return 0


@register.simple_tag(takes_context=True)
def cafe_orders(context,limit=12):
    user=context.get('user')
    if not user or not user.is_authenticated:
        return []
    account=getattr(user,'cafe_account',None)
    if not account or not account.approved or not account.active:
        return []
    return user.orders.filter(order_type='cafe').select_related('delivery_region').prefetch_related('items','payments').order_by('-delivery_date','-created_at')[:limit]


@register.simple_tag
def cafe_note_for(order):
    if not order or order.order_type!='cafe' or not order.delivery_date:
        return None
    note=ensure_cafe_note(order)
    return maybe_lock_cafe_note(note) if note else None


@register.simple_tag
def cafe_order_can_edit(order):
    return cafe_order_editable(order)
