from datetime import date, timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .financial_models import BusinessExpense
from .management_forms import (
    ExpenseForm,
    FinancialSettingsForm,
    FixedCostForm,
    IngredientForm,
    InventoryMovementForm,
    PriceSimulatorForm,
    RecipeForm,
    RecipeIngredientForm,
    SpreadsheetUploadForm,
)
from .management_models import (
    FinancialSettings,
    FixedCost,
    Ingredient,
    IngredientPriceHistory,
    InventoryMovement,
    Recipe,
    RecipeIngredient,
    SpreadsheetImportBatch,
)
from .management_services import management_dashboard, simulate_price, sync_recipe_product_cost
from .models import (
    AvailabilityDay,
    CafeAccount,
    Category,
    Conversation,
    CustomerProfile,
    DeliveryRegion,
    DeliveryRoute,
    EventQuote,
    Message,
    Order,
    Product,
)
from .spreadsheet_io import build_management_workbook, import_management_workbook
from .views_finance import _parse_date, _staff_otp_guard


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

    conversations = (
        Conversation.objects.select_related('order__customer', 'order__delivery_region', 'customer')
        .prefetch_related('messages__sender')
        .order_by('-updated_at')[:28]
    )
    conversation_rows = []
    total_unread = 0
    for conversation in conversations:
        thread = list(conversation.messages.all())
        incoming_unread = sum(
            1 for msg in thread if msg.read_at is None and not msg.sender.is_staff
        )
        total_unread += incoming_unread
        conversation_rows.append({
            'conversation': conversation,
            'messages': thread[-8:],
            'last_message': thread[-1] if thread else None,
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
        EventQuote.objects.select_related('customer', 'converted_order')
        .prefetch_related('items')
        .order_by('-created_at')[:40]
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
        'recipes': Recipe.objects.select_related('product').all()[:250],
        'recipe_ingredients': RecipeIngredient.objects.select_related('recipe', 'ingredient').all()[:400],
        'fixed_costs': FixedCost.objects.all()[:100],
        'recent_expenses': BusinessExpense.objects.order_by('-date', '-created_at')[:80],
        'recent_movements': InventoryMovement.objects.select_related('ingredient').order_by('-date', '-created_at')[:100],
        'recent_imports': SpreadsheetImportBatch.objects.select_related('imported_by')[:12],
        'ingredient_form': IngredientForm(),
        'movement_form': InventoryMovementForm(initial={'date': timezone.localdate()}),
        'recipe_form': RecipeForm(),
        'recipe_ingredient_form': RecipeIngredientForm(),
        'fixed_cost_form': FixedCostForm(initial={'start_date': timezone.localdate()}),
        'expense_form': ExpenseForm(initial={'date': timezone.localdate()}),
        'settings_form': FinancialSettingsForm(instance=FinancialSettings.current()),
        'upload_form': SpreadsheetUploadForm(),
    })


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
def management_conversation_send(request):
    conversation = get_object_or_404(Conversation.objects.select_related('order'), pk=request.POST.get('conversation_id'))
    body = (request.POST.get('body') or '').strip()
    if conversation.closed:
        messages.error(request, 'Esta conversa está encerrada.')
        return _management_redirect('messages')
    if not body:
        messages.error(request, 'Escreva uma mensagem antes de enviar.')
        return _management_redirect('messages')
    if len(body) > 4000:
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
        pass
    messages.success(request, 'Mensagem enviada e salva no histórico do pedido.')
    return _management_redirect('messages')


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
    quote.status = status
    quote.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Evento #{str(quote.public_id)[:8].upper()} → {valid[status]}.')
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
@require_POST
def spreadsheet_import(request):
    form = SpreadsheetUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Envie uma planilha .xlsx válida de até 10 MB.')
        return _management_redirect('data')
    try:
        result = import_management_workbook(form.cleaned_data['file'], user=request.user)
    except Exception:
        messages.error(request, 'A planilha não pôde ser importada. Nenhuma alteração parcial foi mantida.')
        return _management_redirect('data')
    warning = f" Avisos: {'; '.join(result['warnings'])}" if result['warnings'] else ''
    messages.success(
        request,
        f"Planilha importada: {result['ingredients_created']} ingredientes criados, "
        f"{result['ingredients_updated']} atualizados, {result['recipes_created']} receitas criadas, "
        f"{result['recipes_updated']} atualizadas e {result['prices_updated']} preços sincronizados.{warning}",
    )
    return _management_redirect('data')


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
