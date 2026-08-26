import csv
from datetime import date
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import CafeAccount, Order, Product
from .financial_services import (
    business_financial_summary,
    cafe_order_editable,
    ensure_cafe_note,
    maybe_lock_cafe_note,
    refresh_order_financials,
    sales_report,
)
from .services import discount_for, price_for, product_allowed, promotion_for_code


def _approved_cafe_for(user):
    return CafeAccount.objects.filter(user=user, approved=True, active=True).first()


def _staff_otp_guard(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        verified = getattr(request.user, 'is_verified', lambda: False)()
        if not request.user.is_staff or (not verified and not settings.DEMO_ALLOW_ADMIN_WITHOUT_OTP):
            return HttpResponseForbidden('A central financeira exige acesso administrativo com segundo fator verificado.')
        return view(request, *args, **kwargs)
    return wrapped


def _parse_date(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


def _reprice_cafe_order(order, cafe, user, note_text=None):
    subtotal = Decimal('0.00')
    for item in order.items.select_related('product').all():
        unit_price = price_for(user, item.product, item.quantity, 'cafe')
        if unit_price is None:
            raise ValueError(f'Não existe preço B2B válido para {item.product.name}.')
        if item.unit_price != unit_price:
            item.unit_price = unit_price
            item.save(update_fields=['unit_price', 'updated_at'])
        subtotal += unit_price * item.quantity

    minimum = max(order.delivery_region.minimum_order if order.delivery_region else Decimal('0'), cafe.minimum_order)
    if subtotal < minimum:
        raise ValueError(f'O pedido mínimo desta cafeteria/região é R$ {minimum:.2f}.')

    promotion = promotion_for_code(user, order.promotion_code) if order.promotion_code else None
    discount = discount_for(promotion, subtotal)
    order.subtotal = subtotal
    order.discount = discount
    order.total = subtotal - discount + order.delivery_fee
    if note_text is not None:
        order.customer_note = note_text[:1000]
    order.save(update_fields=['subtotal', 'discount', 'total', 'customer_note', 'updated_at'])
    refresh_order_financials(order)
    return order


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
    editable = cafe_order_editable(order)

    if request.method == 'POST':
        if not editable:
            messages.error(request, 'Esta nota já atingiu o horário limite para alterações comerciais.')
            return redirect('cafe_order_edit', public_id=order.public_id)

        action = request.POST.get('action', '').strip()
        try:
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(pk=order.pk)
                locked_note = ensure_cafe_note(locked_order)
                if locked_note:
                    locked_note = maybe_lock_cafe_note(locked_note)
                if not cafe_order_editable(locked_order):
                    raise ValueError('O horário limite desta nota foi atingido.')

                if action == 'quantity':
                    item = get_object_or_404(locked_order.items.select_related('product'), pk=request.POST.get('item_id'))
                    quantity = max(0, min(int(request.POST.get('quantity', item.quantity)), 9999))
                    if quantity == 0:
                        item.delete()
                    else:
                        if not product_allowed(request.user, item.product, 'cafe'):
                            raise ValueError('Produto indisponível para esta cafeteria.')
                        item.quantity = quantity
                        item.save(update_fields=['quantity', 'updated_at'])
                elif action == 'add':
                    product = get_object_or_404(Product, pk=request.POST.get('product_id'), active=True)
                    quantity = max(1, min(int(request.POST.get('quantity', '1')), 9999))
                    if not product_allowed(request.user, product, 'cafe'):
                        raise ValueError('Produto indisponível para esta cafeteria.')
                    existing = locked_order.items.filter(product=product).first()
                    if existing:
                        existing.quantity += quantity
                        existing.save(update_fields=['quantity', 'updated_at'])
                    else:
                        unit_price = price_for(request.user, product, quantity, 'cafe')
                        if unit_price is None:
                            raise ValueError('Produto sem preço B2B válido.')
                        locked_order.items.create(product=product, quantity=quantity, unit_price=unit_price)
                elif action == 'note':
                    pass
                else:
                    raise ValueError('Ação inválida.')

                _reprice_cafe_order(locked_order, cafe, request.user, request.POST.get('customer_note'))
                ensure_cafe_note(locked_order, refresh=True)
            messages.success(request, 'Nota atualizada.')
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect('cafe_order_edit', public_id=order.public_id)

    available_products = [
        product for product in Product.objects.filter(active=True, sell_cafe=True).order_by('category__sort_order', 'sort_order', 'name')
        if product_allowed(request.user, product, 'cafe')
    ]
    return render(request, 'store/cafe_order_edit.html', {
        'order': order,
        'note': note,
        'editable': editable,
        'available_products': available_products,
    })


@_staff_otp_guard
def finance_dashboard(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from'), today.replace(day=1))
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    summary = business_financial_summary(start, end)
    report = sales_report(start, end)
    return render(request, 'store/finance_dashboard.html', {
        'summary': summary,
        'report': report,
        'date_from': start,
        'date_to': end,
    })


@_staff_otp_guard
def finance_export_csv(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from'), today.replace(day=1))
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    report = sales_report(start, end)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="nossas-delicias-{start}-{end}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Canal', 'Pedidos', 'Faturamento', 'Custo', 'Lucro', 'Margem'])
    for row in report['channels']:
        writer.writerow([
            row['order_type'], row['orders'], row['revenue'], row['cost'], row['profit'], row['margin_percent']
        ])
    writer.writerow([])
    writer.writerow(['Produto', 'Qtd', 'Faturamento', 'Custo', 'Lucro', 'Margem'])
    for row in report['products']:
        writer.writerow([
            row['name'], row['quantity'], row['revenue'], row['cost'], row['profit'], row['margin_percent']
        ])
    return response
