import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .forms import AddressForm, CafeApplicationForm, CakeDesignForm, CheckoutForm, EventQuoteForm, ProfileForm, RegisterForm
from .models import (
    CafeAccount,
    CakeDesign,
    CakeOption,
    Cart,
    CartItem,
    BrandProfile,
    CafeLocation,
    Category,
    Conversation,
    CustomerAddress,
    CustomerProfile,
    EventQuote,
    EventQuoteItem,
    EventQuoteMessage,
    Favorite,
    Order,
    Payment,
    Product,
    PromotionRedemption,
)
from .payment_gateway import create_checkout_preference, fetch_payment, validate_webhook
from .services import (
    available_dates,
    can_schedule,
    cart_snapshot,
    customer_order_type,
    discount_for,
    eligible_promotions,
    lock_delivery_slot,
    money,
    product_allowed,
    promotion_for_code,
    region_for_zip,
)


def _visibility_q(order_type):
    return {
        'retail': Q(sell_retail=True),
        'cafe': Q(sell_cafe=True),
        'event': Q(sell_event=True),
    }.get(order_type, Q(sell_retail=True))


def _catalog_order_type(request):
    if request.user.is_authenticated:
        return customer_order_type(request.user)
    return 'retail'


def _cart_context(request, form=None):
    snapshot = cart_snapshot(request.user)
    return {
        'snapshot': snapshot,
        'form': form or CheckoutForm(),
        'addresses': request.user.saved_addresses.all(),
        'promotions': eligible_promotions(request.user),
    }


def home(request):
    order_type = _catalog_order_type(request)
    visible_products = Product.objects.filter(active=True).filter(_visibility_q(order_type))
    categories = Category.objects.filter(active=True).prefetch_related(
        Prefetch('products', queryset=visible_products.order_by('sort_order', 'name'))
    )
    featured = visible_products.filter(featured=True).select_related('category').order_by('sort_order', 'name')[:8]
    brand_profile = BrandProfile.objects.order_by('id').first()
    return render(request, 'store/home.html', {
        'categories': categories,
        'featured': featured,
        'brand_profile': brand_profile,
    })


def catalog(request):
    order_type = _catalog_order_type(request)
    visible_products = Product.objects.filter(active=True).filter(_visibility_q(order_type)).prefetch_related('prices')
    categories = Category.objects.filter(active=True).prefetch_related(
        Prefetch('products', queryset=visible_products.order_by('sort_order', 'name'))
    ).order_by('sort_order', 'name')
    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(request.user.favorite_products.values_list('product_id', flat=True))
    return render(request, 'store/catalog.html', {'categories': categories, 'order_type': order_type, 'favorite_ids': favorite_ids})


@ratelimit(key='ip', rate='10/d', method='POST', block=True)
def cake_studio(request):
    form = CakeDesignForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, 'Entre na sua conta para enviar a composição do bolo.')
            return redirect(f"{reverse('login')}?next={reverse('cake_studio')}")
        if form.is_valid():
            data = form.cleaned_data
            selected = {
                'dough': data['dough'].name,
                'primary_filling': data['primary_filling'].name,
                'secondary_filling': data['secondary_filling'].name if data.get('secondary_filling') else '',
                'complement': data['complement'].name if data.get('complement') else '',
                'frosting': data['frosting'].name,
                'decoration_style': dict(CakeDesign.DECORATION_STYLES)[data['decoration_style']],
            }
            summary_parts = [
                f"Massa: {selected['dough']}",
                f"Recheio: {selected['primary_filling']}",
            ]
            if selected['secondary_filling']:
                summary_parts.append(f"Segundo recheio: {selected['secondary_filling']}")
            if selected['complement']:
                summary_parts.append(f"Complemento: {selected['complement']}")
            summary_parts.extend([
                f"Cobertura: {selected['frosting']}",
                f"Decoração: {selected['decoration_style']}",
            ])
            with transaction.atomic():
                quote = EventQuote.objects.create(
                    customer=request.user,
                    event_type='other',
                    event_date=data['event_date'],
                    guest_count=data['guest_count'],
                    address=data['address'],
                    notes=data.get('notes', ''),
                    status='new',
                )
                CakeDesign.objects.create(
                    quote=quote,
                    dough=data['dough'],
                    primary_filling=data['primary_filling'],
                    secondary_filling=data.get('secondary_filling'),
                    complement=data.get('complement'),
                    frosting=data['frosting'],
                    decoration_style=data['decoration_style'],
                    decoration_notes=data.get('decoration_notes', ''),
                    occasion=data.get('occasion', ''),
                    reference_image=data.get('reference_image'),
                    selection_snapshot=selected,
                )
                EventQuoteItem.objects.create(
                    quote=quote,
                    description='Bolo personalizado · ' + ' · '.join(summary_parts),
                    quantity=1,
                )
                quote.status_history.create(status='new', changed_by=request.user, note='Composição criada no estúdio de bolos.')
            messages.success(request, 'Seu bolo foi enviado para orçamento. Acompanhe a proposta e converse com a equipe por aqui.')
            return redirect('event_quote_detail', public_id=quote.public_id)
    option_groups = {
        kind: CakeOption.objects.filter(kind=kind, active=True).order_by('sort_order', 'name')
        for kind in ('dough', 'filling', 'complement', 'frosting')
    }
    return render(request, 'store/cake_studio.html', {
        'form': form,
        'option_groups': option_groups,
        'decoration_styles': CakeDesign.DECORATION_STYLES,
    })


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def register(request):
    if request.user.is_authenticated:
        return redirect('account')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            CustomerProfile.objects.create(
                user=user,
                marketing_opt_in=form.cleaned_data.get('marketing_opt_in', False),
            )
            Cart.objects.create(user=user)
        login(request, user)
        return redirect('account')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def account(request):
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    orders = request.user.orders.prefetch_related('items__product', 'payments').order_by('-created_at')
    profile_form = ProfileForm(user=request.user, initial={
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'phone': profile.phone,
        'birth_date': profile.birth_date,
        'marketing_opt_in': profile.marketing_opt_in,
    })
    return render(request, 'store/account.html', {
        'profile': profile,
        'orders': orders,
        'promotions': eligible_promotions(request.user),
        'event_quotes': request.user.event_quotes.order_by('-created_at')[:10],
        'profile_form': profile_form,
        'address_form': AddressForm(),
        'addresses': request.user.saved_addresses.order_by('-default', 'label'),
        'favorites': Product.objects.filter(favorited_by__user=request.user, active=True).select_related('category'),
    })


@login_required
@require_POST
@ratelimit(key='user', rate='12/m', method='POST', block=True)
def account_profile_update(request):
    form = ProfileForm(request.POST, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'Seus dados foram atualizados.')
    else:
        messages.error(request, 'Revise os dados do perfil: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('account')


@login_required
@require_POST
@ratelimit(key='user', rate='20/m', method='POST', block=True)
def address_save(request):
    address_id = request.POST.get('address_id')
    instance = get_object_or_404(CustomerAddress, pk=address_id, user=request.user) if address_id else None
    form = AddressForm(request.POST, instance=instance)
    if form.is_valid():
        with transaction.atomic():
            address = form.save(commit=False)
            address.user = request.user
            if address.default:
                request.user.saved_addresses.exclude(pk=address.pk).update(default=False)
            elif not request.user.saved_addresses.exclude(pk=address.pk).exists():
                address.default = True
            address.save()
        messages.success(request, 'Endereço salvo.')
    else:
        messages.error(request, 'Revise o endereço: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('account')


@login_required
@require_POST
def address_delete(request, address_id):
    address = get_object_or_404(CustomerAddress, pk=address_id, user=request.user)
    was_default = address.default
    address.delete()
    if was_default:
        replacement = request.user.saved_addresses.order_by('created_at').first()
        if replacement:
            replacement.default = True
            replacement.save(update_fields=['default', 'updated_at'])
    messages.success(request, 'Endereço removido.')
    return redirect('account')


@login_required
@require_POST
@ratelimit(key='user', rate='60/m', method='POST', block=True)
def favorite_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id, active=True)
    favorite = Favorite.objects.filter(user=request.user, product=product).first()
    if favorite:
        favorite.delete()
        active = False
    else:
        Favorite.objects.create(user=request.user, product=product)
        active = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'favorite': active})
    return redirect('catalog')


@login_required
@require_POST
@ratelimit(key='user', rate='40/m', method='POST', block=True)
def add_to_cart(request):
    try:
        product_id = int(request.POST.get('product_id'))
        requested = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Produto ou quantidade inválidos.'}, status=400)

    product = get_object_or_404(Product, id=product_id, active=True)
    order_type = customer_order_type(request.user)
    if not product_allowed(product, order_type):
        return JsonResponse({'error': 'Este produto não está disponível para o seu perfil.'}, status=403)

    maximum = min(product.stock_limit or 9999, 9999)
    if maximum < product.min_quantity:
        return JsonResponse({'error': 'Produto temporariamente indisponível.'}, status=409)
    quantity = min(max(product.min_quantity, requested), maximum)

    with transaction.atomic():
        cart, _ = Cart.objects.get_or_create(user=request.user)
        Cart.objects.select_for_update().get(pk=cart.pk)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity},
        )
        if not created:
            item.quantity = min(item.quantity + quantity, maximum)
            item.save(update_fields=['quantity', 'updated_at'])
        count = sum(i.quantity for i in cart.items.all())

    return JsonResponse({'ok': True, 'count': count, 'redirect': '/carrinho/'})


@login_required
@require_POST
def update_cart_item(request, item_id):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item = get_object_or_404(CartItem.objects.select_related('product'), id=item_id, cart=cart)
    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        quantity = item.quantity

    if quantity <= 0:
        item.delete()
    else:
        maximum = min(item.product.stock_limit or 9999, 9999)
        item.quantity = min(max(item.product.min_quantity, quantity), maximum)
        item.note = (request.POST.get('note') or '')[:250]
        item.save(update_fields=['quantity', 'note', 'updated_at'])
    return redirect('cart')


@login_required
@require_POST
def remove_cart_item(request, item_id):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    get_object_or_404(CartItem, id=item_id, cart=cart).delete()
    return redirect('cart')


@login_required
def cart_view(request):
    return render(request, 'store/cart.html', _cart_context(request))


@login_required
@require_GET
@ratelimit(key='user', rate='60/m', method='GET', block=True)
def delivery_availability(request):
    region = region_for_zip(request.GET.get('cep', ''))
    if not region:
        return JsonResponse({'available': False, 'error': 'Região ainda não atendida.'}, status=404)
    snapshot = cart_snapshot(request.user)
    lead = snapshot['max_lead'] if snapshot['rows'] else 1
    dates = available_dates(region, lead_days=lead, order_type=snapshot['order_type'])
    return JsonResponse({
        'available': bool(dates),
        'region': region.name,
        'fee': float(region.delivery_fee),
        'minimum_order': float(region.minimum_order),
        'dates': [{
            'date': row['date'].isoformat(),
            'remaining': row['remaining'],
            'start': row['start_time'].strftime('%H:%M'),
            'end': row['end_time'].strftime('%H:%M'),
        } for row in dates],
    })


@login_required
@require_POST
@ratelimit(key='user', rate='10/m', method='POST', block=True)
def checkout_cart(request):
    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return render(request, 'store/cart.html', _cart_context(request, form), status=400)

    region = region_for_zip(form.cleaned_data['zip_code'])
    if not region:
        form.add_error('zip_code', 'Ainda não entregamos nesta região.')
        return render(request, 'store/cart.html', _cart_context(request, form), status=422)

    chosen = form.cleaned_data['delivery_date']
    initial_snapshot = cart_snapshot(request.user)
    if not initial_snapshot['rows']:
        form.add_error(None, 'Sua sacola está vazia ou contém produtos indisponíveis.')
        return render(request, 'store/cart.html', _cart_context(request, form), status=400)
    if not can_schedule(region, chosen, initial_snapshot['max_lead'], order_type=initial_snapshot['order_type']):
        form.add_error('delivery_date', 'Esta data não está mais disponível para este tipo de conta.')
        return render(request, 'store/cart.html', _cart_context(request, form), status=409)

    with transaction.atomic():
        cart = Cart.objects.select_for_update().get(user=request.user)
        snapshot = cart_snapshot(request.user)
        if not snapshot['rows']:
            form.add_error(None, 'A sacola mudou enquanto o pedido era finalizado. Revise os itens.')
            return render(request, 'store/cart.html', _cart_context(request, form), status=409)

        minimum = region.minimum_order
        cafe = getattr(request.user, 'cafe_account', None)
        if snapshot['order_type'] == 'cafe' and cafe and cafe.approved and cafe.active:
            minimum = max(minimum, cafe.minimum_order)
        if snapshot['subtotal'] < minimum:
            form.add_error(None, f'Pedido mínimo para este perfil/região: R$ {minimum:.2f}')
            return render(request, 'store/cart.html', _cart_context(request, form), status=422)

        if not lock_delivery_slot(region, chosen, snapshot['max_lead'], order_type=snapshot['order_type']):
            form.add_error('delivery_date', 'A última vaga desta data acabou de ser ocupada.')
            return render(request, 'store/cart.html', _cart_context(request, form), status=409)

        for row in snapshot['rows']:
            limit = row['product'].stock_limit
            if limit is not None and row['quantity'] > limit:
                form.add_error(None, f'{row["product"].name} não possui essa quantidade disponível.')
                return render(request, 'store/cart.html', _cart_context(request, form), status=409)

        promotion = promotion_for_code(request.user, form.cleaned_data.get('promotion_code'))
        discount = discount_for(promotion, snapshot['subtotal'])
        total = money(snapshot['subtotal'] - discount + region.delivery_fee)

        order = Order.objects.create(
            customer=request.user,
            order_type=snapshot['order_type'],
            status='pending_payment',
            delivery_date=chosen,
            delivery_region=region,
            delivery_address=form.cleaned_data['address'][:1000],
            delivery_fee=region.delivery_fee,
            subtotal=snapshot['subtotal'],
            discount=discount,
            total=total,
            promotion_code=promotion.code if promotion else '',
            customer_note=form.cleaned_data['note'][:1000],
        )
        for row in snapshot['rows']:
            order.items.create(
                product=row['product'],
                quantity=row['quantity'],
                unit_price=row['unit_price'],
                note=row['item'].note,
            )
        Conversation.objects.create(order=order, customer=request.user)
        order.status_history.create(status='pending_payment', changed_by=request.user, note='Pedido criado.')
        if promotion:
            PromotionRedemption.objects.create(
                promotion=promotion,
                user=request.user,
                order=order,
                discount_amount=discount,
            )
        cart.items.all().delete()
        if form.cleaned_data.get('save_address'):
            CustomerAddress.objects.get_or_create(
                user=request.user,
                zip_code=form.cleaned_data['zip_code'],
                street=form.cleaned_data['address'][:180],
                number='s/n',
                defaults={'label': 'Entrega'},
            )

    return redirect('order_detail', public_id=order.public_id)


@login_required
def order_detail(request, public_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'status_history', 'payments'),
        public_id=public_id,
        customer=request.user,
    )
    conversation, _ = Conversation.objects.get_or_create(order=order, defaults={'customer': request.user})
    return render(request, 'store/order_detail.html', {'order': order, 'conversation': conversation})


def cafe_portal(request):
    account = CafeAccount.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    form = None if account or not request.user.is_authenticated else CafeApplicationForm()
    recurring = account.recurring_orders.prefetch_related('items__product') if account and account.approved else []
    saved_locations = {location.slot: location for location in CafeLocation.objects.all()}
    cafe_locations = [saved_locations.get(slot, CafeLocation(slot=slot)) for slot in range(1, 7)]
    return render(request, 'store/cafe.html', {
        'account': account,
        'form': form,
        'recurring': recurring,
        'cafe_locations': cafe_locations,
    })


@login_required
@require_POST
@ratelimit(key='user', rate='3/d', method='POST', block=True)
def cafe_apply(request):
    if CafeAccount.objects.filter(user=request.user).exists():
        return redirect('cafe_portal')
    form = CafeApplicationForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            form.save_for_user(request.user)
            profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
            profile.customer_type = 'cafe'
            profile.save(update_fields=['customer_type', 'updated_at'])
        messages.success(request, 'Cadastro de cafeteria enviado para aprovação. Preços e rotas B2B só são liberados após a autorização da equipe.')
        return redirect('cafe_portal')
    return render(request, 'store/cafe.html', {'form': form, 'account': None}, status=400)


def event_portal(request):
    form = EventQuoteForm()
    quotes = request.user.event_quotes.prefetch_related('items').order_by('-created_at') if request.user.is_authenticated else []
    return render(request, 'store/events.html', {'form': form, 'quotes': quotes})


@login_required
@require_POST
@ratelimit(key='user', rate='8/d', method='POST', block=True)
def event_quote_create(request):
    form = EventQuoteForm(request.POST)
    if form.is_valid():
        quote = form.save(commit=False)
        quote.customer = request.user
        quote.save()
        quote.status_history.create(status='new', changed_by=request.user, note='Solicitação criada pelo cliente.')
        messages.success(request, 'Pedido de orçamento recebido. Você poderá acompanhar pela sua conta.')
        return redirect('event_portal')
    return render(request, 'store/events.html', {'form': form, 'quotes': request.user.event_quotes.all()}, status=400)


@login_required
def event_quote_detail(request, public_id):
    quote = get_object_or_404(
        EventQuote.objects.select_related(
            'cake_design__dough',
            'cake_design__primary_filling',
            'cake_design__secondary_filling',
            'cake_design__complement',
            'cake_design__frosting',
        ).prefetch_related('items__product', 'messages__sender', 'status_history'),
        public_id=public_id,
        customer=request.user,
    )
    quote.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
    return render(request, 'store/event_quote_detail.html', {
        'quote': quote,
        'cake_design': getattr(quote, 'cake_design', None),
    })


@login_required
@require_POST
@ratelimit(key='user', rate='20/m', method='POST', block=True)
def event_quote_message_send(request, public_id):
    quote = get_object_or_404(EventQuote, public_id=public_id, customer=request.user)
    body = (request.POST.get('body') or '').strip()
    if not body:
        messages.error(request, 'Escreva uma mensagem antes de enviar.')
    elif len(body) > 4000:
        messages.error(request, 'A mensagem pode ter no máximo 4.000 caracteres.')
    else:
        EventQuoteMessage.objects.create(quote=quote, sender=request.user, body=body)
        messages.success(request, 'Mensagem enviada para a equipe do evento.')
    return redirect('event_quote_detail', public_id=quote.public_id)


@login_required
@require_POST
@ratelimit(key='user', rate='8/d', method='POST', block=True)
def event_quote_accept(request, public_id):
    with transaction.atomic():
        quote = get_object_or_404(
            EventQuote.objects.select_for_update().prefetch_related('items'),
            public_id=public_id,
            customer=request.user,
        )
        if quote.status not in {'sent', 'negotiation'}:
            messages.error(request, 'Esta proposta não está disponível para aceite.')
            return redirect('event_quote_detail', public_id=quote.public_id)
        rows = list(quote.items.all())
        if not rows or any(row.proposed_unit_price is None for row in rows):
            messages.error(request, 'A proposta precisa estar completa antes do aceite.')
            return redirect('event_quote_detail', public_id=quote.public_id)
        total = money(sum((row.proposed_unit_price * row.quantity for row in rows), Decimal('0')))
        quote.status = 'accepted'
        quote.final_total = total
        quote.save(update_fields=['status', 'final_total', 'updated_at'])
        quote.status_history.create(status='accepted', changed_by=request.user, note='Proposta aceita pelo cliente.')
    messages.success(request, 'Proposta aceita. A equipe agora poderá convertê-la em pedido.')
    return redirect('event_quote_detail', public_id=quote.public_id)


@login_required
@require_POST
@ratelimit(key='user', rate='10/m', method='POST', block=True)
def start_payment(request, public_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        public_id=public_id,
        customer=request.user,
        status='pending_payment',
    )
    try:
        preference = create_checkout_preference(request, order)
    except RuntimeError as exc:
        return JsonResponse({'error': str(exc)}, status=503)

    Payment.objects.get_or_create(
        order=order,
        provider='mercado_pago',
        provider_id=str(preference['id'])[:160],
        defaults={
            'status': 'pending',
            'amount': order.total,
            'method': 'checkout_pro',
            'raw_reference': {'preference_id': str(preference['id'])[:160]},
        },
    )
    return JsonResponse({'checkout_url': preference['init_point']})


@login_required
def payment_return(request):
    reference = request.GET.get('external_reference')
    if reference:
        order = Order.objects.filter(public_id=reference, customer=request.user).first()
        if order:
            return redirect('order_detail', public_id=order.public_id)
    return redirect('account')


@csrf_exempt
@require_POST
@ratelimit(key='ip', rate='120/m', method='POST', block=True)
def mercado_pago_webhook(request):
    if not validate_webhook(request):
        return HttpResponse(status=401)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    provider_id = str((payload.get('data') or {}).get('id') or request.GET.get('data.id') or '')[:160]
    if not provider_id:
        return HttpResponse(status=400)
    try:
        remote = fetch_payment(provider_id)
    except RuntimeError:
        return HttpResponse(status=503)

    reference = remote.get('external_reference')
    if not reference:
        return HttpResponse(status=200)

    mapped = {
        'approved': 'approved',
        'pending': 'pending',
        'in_process': 'pending',
        'rejected': 'rejected',
        'refunded': 'refunded',
        'cancelled': 'cancelled',
    }.get(remote.get('status'), 'pending')

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(public_id=reference).first()
        if not order:
            return HttpResponse(status=200)

        try:
            remote_amount = Decimal(str(remote.get('transaction_amount')))
        except (InvalidOperation, TypeError):
            remote_amount = None
        amount_matches = remote_amount is not None and money(remote_amount) == money(order.total)
        # Mercado Pago always returns the transaction currency. Do not infer a
        # missing value: an approved transaction must explicitly be in BRL.
        currency_matches = remote.get('currency_id') == 'BRL'

        effective_status = mapped
        mismatch = mapped == 'approved' and (not amount_matches or not currency_matches)
        if mismatch:
            effective_status = 'rejected'

        payment, _ = Payment.objects.get_or_create(
            order=order,
            provider='mercado_pago',
            provider_id=provider_id,
            defaults={'amount': order.total},
        )
        payment.status = effective_status
        payment.amount = order.total
        payment.method = str(remote.get('payment_type_id') or remote.get('payment_method_id') or '')[:30]
        payment.raw_reference = {
            'payment_id': provider_id,
            'status': str(remote.get('status', ''))[:40],
            'amount_matches': amount_matches,
            'currency_matches': currency_matches,
        }
        if effective_status == 'approved':
            payment.paid_at = timezone.now()
        payment.save()

        if effective_status == 'approved' and order.status == 'pending_payment':
            order.status = 'paid'
            order.save(update_fields=['status', 'updated_at'])
            order.status_history.create(status='paid', note='Pagamento confirmado pelo Mercado Pago.')

    return HttpResponse(status=200)
