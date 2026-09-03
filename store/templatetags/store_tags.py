from django import template
from django.templatetags.static import static
from store.models import ProductPrice
from store.services import price_for
from store.financial_services import cafe_order_editable, ensure_cafe_note, maybe_lock_cafe_note

register=template.Library()


_CATEGORY_STORIES = {
    'brownies': {
        'title': 'O intervalo do dia merece uma camada extra de chocolate.',
        'description': 'Brownies de centro macio, casquinha delicada e aquele cheiro que faz a pausa parecer um pequeno ritual.',
        'note': 'Perfeitos para o café, para dividir ou guardar só para você.',
        'image': 'images/showcase/catalog/brownie-classic.webp',
        'alt': 'Brownies artesanais em um prato claro',
        'tone': 'cocoa',
    },
    'bolos-fatias': {
        'title': 'Uma fatia bonita tem o poder de mudar o ritmo da tarde.',
        'description': 'Bolos e fatias com sabor de receita feita com calma, para acompanhar conversa, café e vontade de comemorar sem data marcada.',
        'note': 'Escolhas para aproveitar agora, sem abrir mão do capricho.',
        'image': 'images/showcase/catalog/cake-slice.webp',
        'alt': 'Fatia de bolo de chocolate com acabamento artesanal',
        'tone': 'rose',
    },
    'caixas-presentes': {
        'title': 'Presentear fica mais gostoso quando vem em uma caixa pensada nos detalhes.',
        'description': 'Combinações para agradecer, surpreender e dividir. Você escolhe a ocasião; a gente cuida da parte mais gostosa.',
        'note': 'Um mimo para chegar com cara de presente de verdade.',
        'image': 'images/showcase/catalog/gift-box.webp',
        'alt': 'Caixa de presentes com doces artesanais',
        'tone': 'caramel',
    },
    'tortas-e-bolos': {
        'title': 'A mesa começa pela sobremesa que todo mundo vai lembrar.',
        'description': 'Tortas e bolos para aniversários, encontros e dias que pedem uma sobremesa feita especialmente para a ocasião.',
        'note': 'Quer personalizar? Nosso ateliê de bolos guia cada escolha.',
        'image': 'images/showcase/catalog/cake-slice.webp',
        'alt': 'Bolo de chocolate servido em fatia',
        'tone': 'paper',
    },
    'brigadeiros-gourmet': {
        'title': 'Pequenos em tamanho, enormes na lembrança da mesa.',
        'description': 'Brigadeiros gourmet para montar combinações cheias de textura, sabores clássicos e escolhas autorais.',
        'note': 'Para celebrar, montar lembranças e deixar a mesa mais convidativa.',
        'image': 'images/showcase/catalog/brigadeiro.webp',
        'alt': 'Seleção de brigadeiros em forminhas',
        'tone': 'cocoa',
    },
    'brownies-e-doces': {
        'title': 'Chocolate de verdade, feito para render comentários entre uma mordida e outra.',
        'description': 'Brownies e doces em tamanhos e acabamentos para compartilhar, presentear ou montar uma mesa mais gostosa.',
        'note': 'Caixas, unidades e combinações para a sua próxima ocasião.',
        'image': 'images/showcase/catalog/brownie-stack.webp',
        'alt': 'Brownies de chocolate em camadas',
        'tone': 'rose',
    },
    'doces-para-eventos': {
        'title': 'Quando o doce entra em cena, a ocasião fica ainda mais memorável.',
        'description': 'Doces para compor mesas, lembranças e celebrações com quantidades e combinações que acompanham o tamanho do encontro.',
        'note': 'Para eventos, a gente também prepara uma proposta sob medida.',
        'image': 'images/showcase/catalog/event-sweets.webp',
        'alt': 'Mesa de doces preparada para uma celebração',
        'tone': 'caramel',
    },
}

_DEFAULT_CATEGORY_STORY = {
    'title': 'Uma escolha gostosa para entrar no seu momento.',
    'description': 'Receitas preparadas com cuidado, prontas para acompanhar cafés, encontros e celebrações.',
    'note': 'Veja as opções disponíveis e encontre a sua favorita.',
    'image': 'images/showcase/catalog/brownie-box.webp',
    'alt': 'Doces artesanais Nossas Delícias',
    'tone': 'paper',
}


@register.simple_tag
def category_story(category):
    """Return display-only editorial context for a public menu category."""
    slug = (getattr(category, 'slug', '') or '').lower()
    return _CATEGORY_STORIES.get(slug, _DEFAULT_CATEGORY_STORY)


def _product_fallback_filename(product):
    slug = (getattr(product, 'slug', '') or '').lower()
    category = (getattr(getattr(product, 'category', None), 'slug', '') or '').lower()
    name = (getattr(product, 'name', '') or '').lower()
    search_key = f'{slug} {category} {name}'

    if slug == 'bolo-personalizado-monte-o-seu':
        filename = 'bolo-personalizado.webp'
    elif 'banoffee' in search_key:
        filename = 'banoffee-brownies.webp'
    elif any(term in search_key for term in ('camafeu', 'bem-casado', 'evento')):
        filename = 'catalog/event-sweets.webp'
    elif any(term in search_key for term in ('caixa', 'presente', 'kit', 'nd-cx')):
        filename = 'catalog/gift-box.webp'
    elif 'brownie' in search_key or 'nd-br' in search_key:
        if any(term in search_key for term in ('tradicional', 'nd-br-001')):
            filename = 'catalog/brownie-classic.webp'
        elif any(term in search_key for term in ('brigadeiro', 'ninho', 'recheado')):
            filename = 'catalog/brownie-stack.webp'
        else:
            filename = 'catalog/brownie-classic.webp'
    elif 'brigadeiro' in search_key:
        filename = 'catalog/brigadeiro.webp'
    elif any(term in search_key for term in ('fatia', 'bolo', 'torta')):
        filename = 'catalog/cake-slice.webp'
    else:
        filename = 'catalog/brownie-box.webp'
    return filename


@register.simple_tag
def product_fallback_visual(product):
    return static(f'images/showcase/{_product_fallback_filename(product)}')


@register.simple_tag
def product_visual(product):
    """Return an uploaded image when available and a local, reliable showcase otherwise."""
    if product and product.image:
        image_name = (getattr(product.image, 'name', '') or '').lstrip('/')
        # The demo catalogue used symbolic paths before real showcase assets
        # existed. Never emit those known-broken media URLs in production.
        if image_name.startswith('products/demo/'):
            return product_fallback_visual(product)
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
