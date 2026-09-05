import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .financial_models import BusinessExpense, ProductCostProfile
from .financial_services import refresh_order_financials
from .management_forms import (
    CatalogProductForm,
    DirectSaleForm,
    ExpenseForm,
    FinancialSettingsForm,
    FixedCostForm,
    IngredientForm,
    InventoryMovementForm,
    PriceSimulatorForm,
    RecipeForm,
    RecipeIngredientForm,
)
from .management_models import (
    FinancialSettings,
    FixedCost,
    Ingredient,
    IngredientPriceHistory,
    InventoryMovement,
    Recipe,
    RecipeIngredient,
)
from .management_services import management_dashboard, simulate_price, sync_recipe_product_cost
from .models import (
    AvailabilityDay,
    CafeAccount,
    Category,
    Conversation,
    CustomerProfile,
    DataSubjectRequest,
    DeliveryRegion,
    DeliveryRoute,
    EventQuote,
    EventQuoteMessage,
    Message,
    Order,
    Payment,
    Product,
    ProductPrice,
    PriceTable,
)
from .spreadsheet_io import build_management_workbook
from .views_finance import _parse_date, _staff_otp_guard

logger = logging.getLogger(__name__)


def _period(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from'), today.replace(day=1))
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    return start, end


def _management_redirect(module='overview'):
    return HttpResponseRedirect(f"{reverse('management_center')}#{module}")


def _operations_context(start, end):
    today = timezone.localdate()
    orders_qs = (
        Order.objects.select_related('customer', 'delivery_region')
        .prefetch_related('payments', 'items__product')
        .order_by('-created_at')
    )
    period_orders = orders_qs.filter(created_at__date__range=(start, end))
    order_status = {key: 0 for key, _ in Order.STATUSES}
    for row in period_orders.values('status').annotate(total=Count('id')):
        order_status[row['status']] = row['total']

    latest_message = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at', '-pk')
    conversations = list(
        Conversation.objects.select_related('order__customer', 'order__delivery_region', 'customer')
        .annotate(
            incoming_unread=Count(
                'messages',
                filter=Q(messages__read_at__isnull=True, messages__sender__is_staff=False),
                distinct=True,
            ),
            last_message_body=Subquery(latest_message.values('body')[:1]),
            last_message_at=Subquery(latest_message.values('created_at')[:1]),
        )
        .order_by('-last_message_at', '-updated_at')[:40]
    )
    conversation_rows = []
    total_unread = 0
    for conversation in conversations:
        incoming_unread = conversation.incoming_unread
        total_unread += incoming_unread
        conversation_rows.append({
            'conversation': conversation,
            'unread': incoming_unread,
        })

    cafes = list(
        CafeAccount.objects.select_related('user', 'price_table')
        .annotate(
            order_count=Count(
                'user__orders',
                filter=Q(user__orders__order_type='cafe'),
                distinct=True,
            ),
            order_revenue=Sum(
                'user__orders__total',
                filter=Q(user__orders__order_type='cafe') & ~Q(user__orders__status='cancelled'),
            ),
        )
        .order_by('-approved', '-updated_at')[:40]
    )
    events = list(
        EventQuote.objects.select_related(
            'customer', 'converted_order', 'cake_design__dough', 'cake_design__primary_filling',
            'cake_design__secondary_filling', 'cake_design__complement', 'cake_design__frosting',
        )
        .prefetch_related('items__product', 'messages__sender', 'status_history')
        .order_by('-created_at')[:40]
    )
    privacy_requests = list(
        DataSubjectRequest.objects.select_related('requester', 'resolved_by')
        .order_by('status', '-created_at')[:40]
    )

    regions = list(DeliveryRegion.objects.order_by('-active', 'name'))
    routes = list(DeliveryRoute.objects.prefetch_related('regions').order_by('-active', 'name'))
    availability = {
        row.date: row
        for row in AvailabilityDay.objects.filter(
            date__range=(today, today + timedelta(days=20))
        )
    }
    delivery_orders = list(
        Order.objects.select_related('customer', 'delivery_region')
        .filter(delivery_date__range=(today, today + timedelta(days=13)))
        .exclude(status='cancelled')
        .order_by('delivery_date', 'created_at')
    )
    deliveries_by_date = {}
    for order in delivery_orders:
        deliveries_by_date.setdefault(order.delivery_date, []).append(order)

    active_routes = [route for route in routes if route.active]
    delivery_calendar = []
    for offset in range(14):
        current = today + timedelta(days=offset)
        day_orders = deliveries_by_date.get(current, [])
        override = availability.get(current)
        route_capacity = sum(
            route.default_capacity
            for route in active_routes
            if current.weekday() in route.weekday_set()
        )
        capacity = override.capacity if override else route_capacity
        enabled = override.enabled if override else bool(route_capacity)
        delivery_calendar.append({
            'date': current,
            'orders': day_orders,
            'count': len(day_orders),
            'capacity': capacity,
            'enabled': enabled,
            'note': override.note if override else '',
            'fill_percent': min(100, round((len(day_orders) / capacity) * 100)) if capacity else 0,
        })

    featured = list(
        Product.objects.filter(featured=True, active=True)
        .select_related('category')
        .order_by('sort_order', 'name')[:10]
    )

    return {
        'latest_orders': list(orders_qs[:40]),
        'order_status': order_status,
        'order_status_choices': Order.STATUSES,
        'open_orders': period_orders.exclude(status__in=['completed', 'cancelled']).count(),
        'today_deliveries': sum(1 for row in delivery_orders if row.delivery_date == today),
        'conversation_rows': conversation_rows,
        'unread_messages': total_unread,
        'open_conversations': sum(1 for row in conversation_rows if not row['conversation'].closed),
        'cafes': cafes,
        'pending_cafes': sum(1 for cafe in cafes if not cafe.approved and cafe.active),
        'active_cafes': sum(1 for cafe in cafes if cafe.approved and cafe.active),
        'events': events,
        'new_events': sum(1 for event in events if event.status in {'new', 'review'}),
        'privacy_requests': privacy_requests,
        'pending_privacy_requests': sum(1 for item in privacy_requests if item.status in {'new', 'review', 'waiting'}),
        'privacy_status_choices': DataSubjectRequest.STATUSES,
        'event_status_choices': EventQuote.STATUSES,
        'regions': regions,
        'routes': routes,
        'delivery_calendar': delivery_calendar,
        'featured_products': featured,
        'catalog': {
            'products': Product.objects.count(),
            'active_products': Product.objects.filter(active=True).count(),
            'featured': Product.objects.filter(active=True, featured=True).count(),
            'categories': Category.objects.filter(active=True).count(),
        },
        'customers': {
            'total': CustomerProfile.objects.count(),
            'retail': CustomerProfile.objects.filter(customer_type='retail').count(),
            'cafe': CustomerProfile.objects.filter(customer_type='cafe').count(),
            'event': CustomerProfile.objects.filter(customer_type='event').count(),
        },
    }


@_staff_otp_guard
def management_center(request):
    start, end = _period(request)
    dashboard = management_dashboard(start, end)
    return render(request, 'store/management_center.html', {
        'start': start,
        'end': end,
        'dashboard': dashboard,
        'operations': _operations_context(start, end),
        'ingredients': Ingredient.objects.all()[:250],
        'recipes': Recipe.objects.select_related('product').prefetch_related('ingredients__ingredient').all()[:250],
        'fixed_costs': FixedCost.objects.all()[:100],
        'recent_expenses': BusinessExpense.objects.order_by('-date', '-created_at')[:80],
        'recent_movements': InventoryMovement.objects.select_related('ingredient').order_by('-date', '-created_at')[:100],
        'ingredient_form': IngredientForm(),
        'movement_form': InventoryMovementForm(initial={'date': timezone.localdate()}),
        'recipe_form': RecipeForm(),
        'recipe_ingredient_form': RecipeIngredientForm(),
        'fixed_cost_form': FixedCostForm(initial={'start_date': timezone.localdate()}),
        'expense_form': ExpenseForm(initial={'date': timezone.localdate()}),
        'settings_form': FinancialSettingsForm(instance=FinancialSettings.current()),
        'catalog_product_form': CatalogProductForm(),
        'direct_sale_form': DirectSaleForm(initial={'sale_date': timezone.localdate()}),
    })


def _unique_product_slug(name, current=None):
    base = slugify(name)[:120] or 'produto'
    candidate = base
    suffix = 2
    queryset = Product.objects.exclude(pk=getattr(current, 'pk', None))
    while queryset.filter(slug=candidate).exists():
        candidate = f'{base[:112]}-{suffix}'
        suffix += 1
    return candidate


@_staff_otp_guard
@require_POST
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def management_product_save(request):
    form = CatalogProductForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Produto não salvo: ' + '; '.join(sum(form.errors.values(), [])))
        return _management_redirect('portfolio')
    data = form.cleaned_data
    try:
        with transaction.atomic():
            selected = data.get('product')
            product = Product.objects.select_for_update().filter(pk=selected.pk).first() if selected else Product()
            product.category = data['category']
            product.name = ' '.join(data['name'].split())
            product.slug = product.slug if product.pk else _unique_product_slug(product.name)
            product.description = data['description'].strip()
            if data.get('image'):
                product.image = data['image']
            elif not product.pk:
                product.image = ''
            for field in ('active', 'featured', 'sell_retail', 'sell_cafe', 'sell_event', 'min_quantity', 'lead_time_days', 'stock_limit'):
                setattr(product, field, data[field])
            product.save()

            table_names = {'retail': 'Varejo', 'cafe': 'Cafeterias', 'event': 'Eventos'}
            for kind, field in (('retail', 'retail_price'), ('cafe', 'cafe_price'), ('event', 'event_price')):
                price = data.get(field)
                if price is None:
                    continue
                table, _ = PriceTable.objects.get_or_create(name=table_names[kind], kind=kind, defaults={'active': True})
                ProductPrice.objects.update_or_create(
                    product=product,
                    table=table,
                    min_quantity=product.min_quantity,
                    defaults={'unit_price': price},
                )

            if data.get('production_cost') is not None or data.get('sku'):
                raw_sku = (data.get('sku') or f'ND-{product.pk:04d}').strip().upper()
                conflict = ProductCostProfile.objects.filter(sku=raw_sku).exclude(product=product).exists()
                sku = f'{raw_sku[:33]}-{product.pk}' if conflict else raw_sku
                ProductCostProfile.objects.update_or_create(
                    product=product,
                    defaults={
                        'sku': sku,
                        'sale_unit': data['sale_unit'],
                        'yield_quantity': data['yield_quantity'],
                        'production_cost': data.get('production_cost') or Decimal('0'),
                        'source_reference': 'Cadastro pela Central de Gestão',
                        'active': product.active,
                    },
                )
    except Exception:
        logger.exception('Falha ao salvar produto pela central para o usuário %s.', request.user.pk)
        messages.error(request, 'Não foi possível salvar o produto. Nenhuma alteração parcial foi mantida.')
        return _management_redirect('portfolio')
    messages.success(request, f'{product.name} salvo com canais, preços e custo integrados.')
    return _management_redirect('portfolio')


@_staff_otp_guard
@require_POST
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def management_direct_sale(request):
    form = DirectSaleForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Venda não registrada: ' + '; '.join(sum(form.errors.values(), [])))
        return _management_redirect('orders')
    data = form.cleaned_data
    try:
        with transaction.atomic():
            customer = data.get('customer')
            if customer is None:
                email = data['customer_email'].strip().lower()
                customer = User.objects.filter(email__iexact=email, is_staff=False).first()
                if customer is None:
                    username = email[:150]
                    suffix = 2
                    while User.objects.filter(username=username).exists():
                        marker = f'-{suffix}'
                        username = f'{email[:150 - len(marker)]}{marker}'
                        suffix += 1
                    customer = User(username=username, email=email)
                    name_parts = data['customer_name'].strip().split(maxsplit=1)
                    customer.first_name = name_parts[0]
                    customer.last_name = name_parts[1] if len(name_parts) > 1 else ''
                    customer.set_unusable_password()
                    customer.save()
                    CustomerProfile.objects.get_or_create(user=customer)
            if data['order_type'] == 'cafe':
                cafe_account = CafeAccount.objects.filter(
                    user=customer,
                    approved=True,
                    active=True,
                ).first()
                if cafe_account is None:
                    raise ValueError('Vendas de cafeteria exigem uma conta empresarial ativa e aprovada.')
            product = Product.objects.select_for_update().get(pk=data['product'].pk, active=True)
            quantity = data['quantity']
            if product.stock_limit is not None and quantity > product.stock_limit:
                raise ValueError(f'Estoque disponível de {product.name}: {product.stock_limit}.')
            if not getattr(product, f"sell_{data['order_type']}", False):
                raise ValueError('Este produto não está liberado para o canal escolhido.')
            price = data.get('unit_price')
            if price is None:
                price_row = ProductPrice.objects.filter(
                    product=product,
                    table__active=True,
                    table__kind=data['order_type'],
                    min_quantity__lte=quantity,
                ).order_by('-min_quantity', '-updated_at').first()
                price = price_row.unit_price if price_row else None
            if price is None:
                raise ValueError('Cadastre um preço para o canal ou informe o preço unitário desta venda.')
            total = (price * quantity).quantize(Decimal('0.01'))
            paid = data['payment_status'] == 'approved'
            order = Order.objects.create(
                customer=customer,
                order_type=data['order_type'],
                status='completed' if paid else 'pending_payment',
                delivery_date=data['sale_date'],
                subtotal=total,
                total=total,
                customer_note=data.get('note', ''),
                internal_note=f'Venda direta registrada por {request.user.get_username()}.',
            )
            order.items.create(product=product, quantity=quantity, unit_price=price, note='Venda direta')
            Payment.objects.create(
                order=order,
                provider='manual',
                provider_id=f'manual-{uuid.uuid4()}',
                status=data['payment_status'],
                amount=total,
                method=data['payment_method'],
                paid_at=timezone.now() if paid else None,
                raw_reference={'created_by': request.user.pk, 'source': 'management_direct_sale'},
            )
            Conversation.objects.create(order=order, customer=customer)
            order.status_history.create(status=order.status, changed_by=request.user, note='Venda direta registrada na Central de Gestão.')
            refresh_order_financials(order)
            if product.stock_limit is not None:
                product.stock_limit -= quantity
                product.save(update_fields=['stock_limit', 'updated_at'])
    except ValueError as exc:
        messages.error(request, str(exc))
        return _management_redirect('orders')
    messages.success(request, f'Venda #{str(order.public_id)[:8].upper()} registrada e incluída no financeiro.')
    return _management_redirect('orders')


@_staff_otp_guard
@require_POST
def management_order_status(request):
    order = get_object_or_404(Order, pk=request.POST.get('order_id'))
    status = request.POST.get('status')
    valid = dict(Order.STATUSES)
    if status not in valid:
        messages.error(request, 'Status de pedido inválido.')
        return _management_redirect('orders')
    if order.status != status:
        order.status = status
        order.save(update_fields=['status', 'updated_at'])
        order.status_history.create(
            status=status,
            changed_by=request.user,
            note='Atualizado pela Central de Operação.',
        )
        messages.success(request, f'Pedido #{str(order.public_id)[:8].upper()} → {valid[status]}.')
    return _management_redirect('orders')


@_staff_otp_guard
@require_POST
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def management_conversation_send(request):
    conversation = get_object_or_404(Conversation.objects.select_related('order'), pk=request.POST.get('conversation_id'))
    body = (request.POST.get('body') or '').strip()
    if conversation.closed:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Esta conversa está encerrada.'}, status=409)
        messages.error(request, 'Esta conversa está encerrada.')
        return _management_redirect('messages')
    if not body:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Escreva uma mensagem antes de enviar.'}, status=400)
        messages.error(request, 'Escreva uma mensagem antes de enviar.')
        return _management_redirect('messages')
    if len(body) > 4000:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'A mensagem pode ter no máximo 4.000 caracteres.'}, status=400)
        messages.error(request, 'A mensagem pode ter no máximo 4.000 caracteres.')
        return _management_redirect('messages')

    msg = Message.objects.create(conversation=conversation, sender=request.user, body=body)
    conversation.messages.filter(read_at__isnull=True).exclude(sender__is_staff=True).update(read_at=timezone.now())
    try:
        async_to_sync(get_channel_layer().group_send)(
            f'order_chat_{conversation.order.public_id}',
            {
                'type': 'chat.message',
                'payload': {
                    'id': msg.id,
                    'message': msg.body,
                    'sender_id': request.user.id,
                    'created_at': msg.created_at.isoformat(),
                },
            },
        )
    except Exception:
        # The message is already safely persisted; websocket delivery can recover on reconnect.
        logger.warning('Falha ao publicar resposta administrativa no WebSocket da conversa %s.', conversation.pk, exc_info=True)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'message': {
            'id': msg.pk,
            'body': msg.body,
            'from_team': True,
            'author': 'Nossas Delícias',
            'created_at': timezone.localtime(msg.created_at).strftime('%d/%m %H:%M'),
        }})
    messages.success(request, 'Mensagem enviada e salva no histórico do pedido.')
    return _management_redirect('messages')


@_staff_otp_guard
@require_GET
def management_conversation_thread(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related('order', 'customer'),
        pk=conversation_id,
    )
    thread = list(
        conversation.messages.select_related('sender')
        .order_by('-created_at', '-pk')[:80]
    )
    thread.reverse()
    conversation.messages.filter(
        read_at__isnull=True,
        sender__is_staff=False,
    ).update(read_at=timezone.now())
    return JsonResponse({
        'conversation_id': conversation.pk,
        'closed': conversation.closed,
        'messages': [{
            'id': msg.pk,
            'body': msg.body,
            'from_team': msg.sender.is_staff,
            'author': 'Nossas Delícias' if msg.sender.is_staff else (msg.sender.first_name or msg.sender.username),
            'created_at': timezone.localtime(msg.created_at).strftime('%d/%m %H:%M'),
        } for msg in thread],
    })


@_staff_otp_guard
@require_POST
def management_conversation_read(request):
    conversation = get_object_or_404(Conversation, pk=request.POST.get('conversation_id'))
    conversation.messages.filter(read_at__isnull=True).exclude(sender__is_staff=True).update(read_at=timezone.now())
    return _management_redirect('messages')


@_staff_otp_guard
@require_POST
def management_conversation_toggle(request):
    conversation = get_object_or_404(Conversation, pk=request.POST.get('conversation_id'))
    conversation.closed = not conversation.closed
    conversation.save(update_fields=['closed', 'updated_at'])
    messages.success(request, 'Conversa reaberta.' if not conversation.closed else 'Conversa encerrada.')
    return _management_redirect('messages')


@_staff_otp_guard
@require_POST
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def management_privacy_request_update(request):
    item = get_object_or_404(DataSubjectRequest, pk=request.POST.get('request_id'))
    status = request.POST.get('status')
    if status not in dict(DataSubjectRequest.STATUSES):
        messages.error(request, 'Status de solicitação de dados inválido.')
        return _management_redirect('privacy')
    item.status = status
    item.resolution_note = (request.POST.get('resolution_note') or '').strip()[:1200]
    update_fields = ['status', 'resolution_note', 'updated_at']
    if status in {'resolved', 'rejected'}:
        item.resolved_by = request.user
        item.resolved_at = timezone.now()
        update_fields.extend(['resolved_by', 'resolved_at'])
    else:
        item.resolved_by = None
        item.resolved_at = None
        update_fields.extend(['resolved_by', 'resolved_at'])
    item.save(update_fields=update_fields)
    messages.success(request, 'Solicitação de dados atualizada e registrada para acompanhamento interno.')
    return _management_redirect('privacy')


@_staff_otp_guard
@require_POST
def management_cafe_action(request):
    cafe = get_object_or_404(CafeAccount, pk=request.POST.get('cafe_id'))
    action = request.POST.get('action')
    if action == 'approve':
        cafe.approved = True
        cafe.active = True
        text = 'Cafeteria aprovada.'
    elif action == 'suspend':
        cafe.active = False
        text = 'Cafeteria suspensa.'
    elif action == 'activate':
        cafe.active = True
        text = 'Cafeteria reativada.'
    else:
        messages.error(request, 'Ação de cafeteria inválida.')
        return _management_redirect('cafes')
    cafe.save(update_fields=['approved', 'active', 'updated_at'])
    messages.success(request, text)
    return _management_redirect('cafes')


@_staff_otp_guard
@require_POST
def management_event_status(request):
    quote = get_object_or_404(EventQuote, pk=request.POST.get('quote_id'))
    status = request.POST.get('status')
    valid = dict(EventQuote.STATUSES)
    if status not in valid:
        messages.error(request, 'Status de evento inválido.')
        return _management_redirect('events')
    if quote.status != status:
        quote.status = status
        quote.save(update_fields=['status', 'updated_at'])
        quote.status_history.create(status=status, changed_by=request.user, note='Etapa atualizada pela Central de Operação.')
        messages.success(request, f'Evento #{str(quote.public_id)[:8].upper()} → {valid[status]}.')
    return _management_redirect('events')


@_staff_otp_guard
@require_POST
def management_event_message_send(request):
    quote = get_object_or_404(EventQuote, pk=request.POST.get('quote_id'))
    body = (request.POST.get('body') or '').strip()
    if not body:
        messages.error(request, 'Escreva uma mensagem antes de enviar.')
    elif len(body) > 4000:
        messages.error(request, 'A mensagem pode ter no máximo 4.000 caracteres.')
    else:
        EventQuoteMessage.objects.create(quote=quote, sender=request.user, body=body)
        quote.messages.filter(read_at__isnull=True).exclude(sender__is_staff=True).update(read_at=timezone.now())
        messages.success(request, 'Resposta enviada e vinculada ao orçamento.')
    return _management_redirect('events')


@_staff_otp_guard
@require_POST
def management_event_convert(request):
    quote = get_object_or_404(EventQuote, pk=request.POST.get('quote_id'))
    try:
        with transaction.atomic():
            quote = EventQuote.objects.select_for_update().prefetch_related('items__product').get(pk=quote.pk)
            if quote.converted_order_id:
                messages.info(request, 'Este orçamento já possui um pedido vinculado.')
                return _management_redirect('events')
            if quote.status != 'accepted':
                raise ValueError('O cliente precisa aceitar a proposta antes da conversão.')
            rows = list(quote.items.all())
            if not rows:
                raise ValueError('Adicione ao menos um item ao orçamento antes de converter.')
            if any(not row.product_id or row.proposed_unit_price is None for row in rows):
                raise ValueError('Todos os itens precisam de produto e preço unitário antes da conversão.')
            subtotal = sum((row.proposed_unit_price * row.quantity for row in rows), Decimal('0'))
            order = Order.objects.create(
                customer=quote.customer,
                order_type='event',
                status='pending_payment',
                delivery_date=quote.event_date,
                delivery_address=quote.address,
                subtotal=subtotal,
                total=subtotal,
                customer_note=quote.notes,
                internal_note=f'Convertido do orçamento de evento #{str(quote.public_id)[:8].upper()}.',
            )
            for row in rows:
                order.items.create(
                    product=row.product,
                    quantity=row.quantity,
                    unit_price=row.proposed_unit_price,
                    note=row.description[:250],
                )
            Conversation.objects.create(order=order, customer=quote.customer)
            order.status_history.create(status='pending_payment', changed_by=request.user, note='Pedido criado a partir do orçamento aceito.')
            quote.converted_order = order
            quote.final_total = subtotal
            quote.status = 'converted'
            quote.save(update_fields=['converted_order', 'final_total', 'status', 'updated_at'])
            quote.status_history.create(status='converted', changed_by=request.user, note=f'Convertido no pedido #{str(order.public_id)[:8].upper()}.')
    except ValueError as exc:
        messages.error(request, str(exc))
        return _management_redirect('events')
    messages.success(request, f'Orçamento convertido no pedido #{str(order.public_id)[:8].upper()}.')
    return _management_redirect('events')


@_staff_otp_guard
@require_POST
def management_availability_save(request):
    try:
        selected_date = date.fromisoformat(request.POST.get('date') or '')
        capacity = max(0, min(int(request.POST.get('capacity') or 0), 10000))
    except (TypeError, ValueError):
        messages.error(request, 'Data ou capacidade inválida.')
        return _management_redirect('logistics')
    enabled = request.POST.get('enabled') == '1'
    note = (request.POST.get('note') or '')[:200]
    AvailabilityDay.objects.update_or_create(
        date=selected_date,
        defaults={'enabled': enabled, 'capacity': capacity, 'note': note},
    )
    messages.success(request, f'Disponibilidade de {selected_date.strftime("%d/%m/%Y")} atualizada.')
    return _management_redirect('logistics')


@_staff_otp_guard
@require_POST
def ingredient_save(request):
    pk = request.POST.get('id')
    instance = get_object_or_404(Ingredient, pk=pk) if pk else None
    old_price = instance.package_price if instance else None
    old_quantity = instance.package_quantity if instance else None
    form = IngredientForm(request.POST, instance=instance)
    if form.is_valid():
        ingredient = form.save()
        changed = instance is None or old_price != ingredient.package_price or old_quantity != ingredient.package_quantity
        if changed:
            IngredientPriceHistory.objects.create(
                ingredient=ingredient,
                package_price=ingredient.package_price,
                package_quantity=ingredient.package_quantity,
                unit_cost=ingredient.unit_cost,
                supplier=ingredient.supplier,
                source='Central de Gestão',
                effective_date=timezone.localdate(),
            )
        for recipe in Recipe.objects.filter(ingredients__ingredient=ingredient).distinct():
            sync_recipe_product_cost(recipe)
        messages.success(request, f'{ingredient.name} salvo. Custo unitário: R$ {ingredient.unit_cost:.6f}.')
    else:
        messages.error(request, 'Não foi possível salvar o ingrediente: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('production')


@_staff_otp_guard
@require_POST
def inventory_move(request):
    form = InventoryMovementForm(request.POST)
    if form.is_valid():
        movement = form.save(commit=False)
        movement.created_by = request.user
        movement.save()
        messages.success(request, f'Movimentação registrada para {movement.ingredient.name}.')
    else:
        messages.error(request, 'Movimentação inválida: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('production')


@_staff_otp_guard
@require_POST
def recipe_save(request):
    pk = request.POST.get('id')
    instance = get_object_or_404(Recipe, pk=pk) if pk else None
    form = RecipeForm(request.POST, instance=instance)
    if form.is_valid():
        recipe = form.save()
        sync_recipe_product_cost(recipe)
        messages.success(request, f'Ficha técnica {recipe.code} salva. Custo unitário atual: R$ {recipe.unit_cost:.4f}.')
    else:
        messages.error(request, 'Não foi possível salvar a receita: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('production')


@_staff_otp_guard
@require_POST
def recipe_ingredient_save(request):
    form = RecipeIngredientForm(request.POST)
    if form.is_valid():
        row = form.save()
        sync_recipe_product_cost(row.recipe)
        messages.success(request, f'{row.ingredient.name} vinculado a {row.recipe.code}.')
    else:
        messages.error(request, 'Não foi possível adicionar o ingrediente à receita: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('production')


@_staff_otp_guard
@require_POST
def fixed_cost_save(request):
    form = FixedCostForm(request.POST)
    if form.is_valid():
        cost = form.save()
        messages.success(request, f'Custo fixo “{cost.name}” salvo.')
    else:
        messages.error(request, 'Custo fixo inválido: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('finance')


@_staff_otp_guard
@require_POST
def expense_save(request):
    form = ExpenseForm(request.POST, request.FILES)
    if form.is_valid():
        expense = form.save(commit=False)
        expense.created_by = request.user
        expense.save()
        messages.success(request, f'Despesa “{expense.description}” registrada.')
    else:
        messages.error(request, 'Despesa inválida: ' + '; '.join(sum(form.errors.values(), [])))
    return _management_redirect('finance')


@_staff_otp_guard
@require_POST
def financial_settings_save(request):
    settings = FinancialSettings.current()
    form = FinancialSettingsForm(request.POST, instance=settings)
    if form.is_valid():
        form.save()
        messages.success(request, 'Regras de margem, taxas e contingência atualizadas.')
    else:
        messages.error(request, 'Configuração financeira inválida.')
    return _management_redirect('pricing')


@_staff_otp_guard
def management_export_xlsx(request):
    start, end = _period(request)
    stream = build_management_workbook(start, end)
    response = HttpResponse(
        stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="nossas-delicias-gestao-{start}-{end}.xlsx"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@_staff_otp_guard
def pricing_simulator(request):
    form = PriceSimulatorForm(request.POST or None)
    result = None
    if request.method == 'POST' and form.is_valid():
        result = simulate_price(
            form.cleaned_data['recipe'],
            current_price=form.cleaned_data.get('current_price'),
            desired_margin=form.cleaned_data.get('desired_margin'),
            increase_percent=form.cleaned_data.get('increase_percent'),
            quantity=form.cleaned_data.get('quantity'),
        )
    return render(request, 'store/pricing_simulator.html', {'form': form, 'result': result})
