import csv
from datetime import date
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import CafeAccount, Order
from .financial_models import CafeDeliveryNote
from .financial_services import (
    business_financial_summary,
    cafe_order_editable,
    ensure_cafe_note,
    maybe_lock_cafe_note,
    refresh_order_financials,
    sales_report,
)
from .services import discount_for, price_for, promotion_for_code


def _approved_cafe_for(user):
    return CafeAccount.objects.filter(user=user, approved=True, active=True).first()


def _staff_otp_guard(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        verified = getattr(request.user, 'is_verified', lambda: False)()
        if not request.user.is_staff or not verified:
            return HttpResponseForbidden('A central financeira exige acesso administrativo com segundo fator verificado.')
        return view(request, *args, **kwargs)
    return wrapped


def _parse_date(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


@login_required
@require_http_methods(['GET', 'POST'])
def cafe_order_edit(request, public_id):
    cafe = _approved_cafe_for(request.user)
    if not cafe:
        return HttpResponseForbidden('Conta de cafeteria não aprovada.')

    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'payments'),
        public_id=public_id,
        customer=request.user,
        order_type='cafe',
    )
    note = ensure_cafe_note(order)
    if note:
        note = maybe_lock_cafe_note(note)

    if request.method == 'POST':
        if not cafe_order_editable(order):
            messages.error(request, 'Esta nota já passou do horário de corte e não aceita mais alterações.')
            return redirect('cafe_note', public_id=order.public_id)

        proposals = []
        subtotal = Decimal('0.00')
        for item in order.items.select_related('product').all():
            raw = request.POST.get(f'qty_{item.pk}', str(item.quantity))
            try:
                quantity = max(0, min(int(raw), 9999))
            except (TypeError, ValueError):
                quantity = item.quantity
            if quantity == 0:
                proposals.append((item, 0, None))
                continue
            unit_price = price_for(request.user, item.product, quantity, 'cafe')
            if unit_price is None:
                messages.error(request, f'Não existe preço B2B válido para {item.product.name}.')
                return redirect('cafe_order_edit', public_id=order.public_id)
            proposals.append((item, quantity, unit_price))
            subtotal += unit_price * quantity

        if not any(quantity > 0 for _, quantity, _ in proposals):
            messages.error(request, 'A nota precisa ter pelo menos um item.')
            return redirect('cafe_order_edit', public_id=order.public_id)

        minimum = max(order.delivery_region.minimum_order if order.delivery_region else Decimal('0'), cafe.minimum_order)
        if subtotal < minimum:
            messages.error(request, f'O pedido mínimo desta cafeteria/região é R$ {minimum:.2f}.')
            return redirect('cafe_order_edit', public_id=order.public_id)

        promotion = promotion_for_code(request.user, order.promotion_code) if order.promotion_code else None
        discount = discount_for(promotion, subtotal)
        note_text = (request.POST.get('note') or '')[:1000]

        with transaction.atomic():
            # Lock the order row so two edits from different browser tabs cannot
            # overwrite each other at the same time.
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            if not cafe_order_editable(locked_order):
                messages.error(request, 'O horário de corte foi atingido enquanto você editava. Nenhuma alteração foi salva.')
                return redirect('cafe_note', public_id=order.public_id)

            for item, quantity, unit_price in proposals:
                if quantity == 0:
                    item.delete()
                else:
                    item.quantity = quantity
                    item.unit_price = unit_price
                    item.save(update_fields=['quantity', 'unit_price', 'updated_at'])

            locked_order.subtotal = subtotal
            locked_order.discount = discount
            locked_order.total = subtotal - discount + locked_order.delivery_fee
            locked_order.customer_note = note_text
            locked_order.save(update_fields=['subtotal', 'discount', 'total', 'customer_note', 'updated_at'])
            refresh_order_financials(locked_order)
            locked_order.status_history.create(
                status=locked_order.status,
                changed_by=request.user,
                note='Nota da cafeteria atualizada antes do horário de corte.',
            )

        messages.success(request, 'Nota atualizada. Os valores financeiros foram recalculados.')
        return redirect('cafe_note', public_id=order.public_id)

    return render(request, 'store/cafe_order_edit.html', {
        'cafe': cafe,
        'order': order,
        'note': note,
        'editable': cafe_order_editable(order),
    })


@login_required
def cafe_note(request, public_id):
    cafe = _approved_cafe_for(request.user)
    if not cafe:
        return HttpResponseForbidden('Conta de cafeteria não aprovada.')
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'payments'),
        public_id=public_id,
        customer=request.user,
        order_type='cafe',
    )
    note = ensure_cafe_note(order)
    if note:
        note = maybe_lock_cafe_note(note)
    refresh_order_financials(order)
    rows = [getattr(item, 'financial_snapshot', None) for item in order.items.select_related('product').all()]
    rows = [row for row in rows if row]
    return render(request, 'store/cafe_note.html', {
        'cafe': cafe,
        'order': order,
        'note': note,
        'rows': rows,
        'editable': cafe_order_editable(order),
    })


@_staff_otp_guard
def finance_dashboard(request):
    today = timezone.localdate()
    default_start = today.replace(day=1)
    start = _parse_date(request.GET.get('from'), default_start)
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    report = business_financial_summary(start, end)
    cafe_report = sales_report(start, end, order_type='cafe')
    retail_report = sales_report(start, end, order_type='retail')
    event_report = sales_report(start, end, order_type='event')
    return render(request, 'store/finance_dashboard.html', {
        'report': report,
        'cafe_report': cafe_report,
        'retail_report': retail_report,
        'event_report': event_report,
        'start': start,
        'end': end,
    })


@_staff_otp_guard
def finance_export_csv(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from'), today.replace(day=1))
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    order_type = request.GET.get('type') or None
    if order_type not in {None, 'retail', 'cafe', 'event'}:
        order_type = None
    report = sales_report(start, end, order_type=order_type)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="nossas-delicias-vendas-{start}-{end}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Data', 'Pedido/nota', 'Código', 'Produto', 'Quantidade', 'Preço unitário',
        'Faturamento', 'Custo unitário', 'Custo total', 'Lucro', 'Margem',
        'Pagamento', 'Mês', 'Ano', 'Observações',
    ])
    for snap in report['rows']:
        item = snap.order_item
        order = item.order
        note = getattr(order, 'cafe_delivery_note', None)
        writer.writerow([
            order.delivery_date.strftime('%d/%m/%Y') if order.delivery_date else order.created_at.strftime('%d/%m/%Y'),
            note.note_number if note else str(order.public_id)[:8].upper(),
            snap.sku,
            snap.product_name,
            snap.quantity,
            f'{snap.unit_price:.2f}',
            f'{snap.revenue:.2f}',
            '' if snap.unit_cost is None else f'{snap.unit_cost:.4f}',
            '' if snap.total_cost is None else f'{snap.total_cost:.2f}',
            '' if snap.profit is None else f'{snap.profit:.2f}',
            '' if snap.margin_percent is None else f'{snap.margin_percent:.2f}%',
            'Pago' if order.payments.filter(status='approved').exists() else 'Pendente',
            order.delivery_date.strftime('%m') if order.delivery_date else order.created_at.strftime('%m'),
            order.delivery_date.strftime('%Y') if order.delivery_date else order.created_at.strftime('%Y'),
            order.customer_note,
        ])
    return response
