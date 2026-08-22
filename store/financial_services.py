from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from .models import Order
from .financial_models import (
    BusinessExpense,
    CafeDeliveryNote,
    OrderItemFinancialSnapshot,
    ProductCostProfile,
)

CENT = Decimal('0.01')
HUNDRED = Decimal('100')


def money(value):
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def cafe_cutoff(order):
    """Delivery-day edit deadline: 16:00 in America/Sao_Paulo (project timezone)."""
    if not order.delivery_date:
        return timezone.now()
    naive = datetime.combine(order.delivery_date, time(hour=16, minute=0))
    return timezone.make_aware(naive, timezone.get_current_timezone())


def cafe_note_number(order):
    date_part = order.delivery_date.strftime('%Y%m%d') if order.delivery_date else timezone.localdate().strftime('%Y%m%d')
    return f'ND-CF-{date_part}-{str(order.public_id)[:8].upper()}'


def ensure_cafe_note(order):
    if order.order_type != 'cafe' or not order.delivery_date:
        return None
    cutoff = cafe_cutoff(order)
    note, created = CafeDeliveryNote.objects.get_or_create(
        order=order,
        defaults={'note_number': cafe_note_number(order), 'editable_until': cutoff},
    )
    if not created and note.status == 'draft' and note.locked_at is None and note.editable_until != cutoff:
        note.editable_until = cutoff
        note.save(update_fields=['editable_until', 'updated_at'])
    return note


def cafe_order_editable(order, at=None):
    if order.order_type != 'cafe' or not order.delivery_date:
        return False
    if order.status in {'completed', 'cancelled'}:
        return False
    note = ensure_cafe_note(order)
    now = at or timezone.now()
    return bool(note and note.status == 'draft' and note.locked_at is None and now < note.editable_until)


def refresh_item_financial_snapshot(order_item, allow_locked=False):
    order = order_item.order
    note = ensure_cafe_note(order) if order.order_type == 'cafe' else None
    if note and note.is_locked and not allow_locked:
        return OrderItemFinancialSnapshot.objects.filter(order_item=order_item).first()

    cost_profile = ProductCostProfile.objects.filter(product_id=order_item.product_id, active=True).first()
    unit_cost = cost_profile.unit_cost if cost_profile else None
    revenue = money(Decimal(order_item.unit_price) * order_item.quantity)
    total_cost = money(unit_cost * order_item.quantity) if unit_cost is not None else None
    profit = money(revenue - total_cost) if total_cost is not None else None
    margin = (profit / revenue * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if profit is not None and revenue else None

    snapshot, _ = OrderItemFinancialSnapshot.objects.update_or_create(
        order_item=order_item,
        defaults={
            'sku': cost_profile.sku if cost_profile else '',
            'product_name': order_item.product.name,
            'quantity': order_item.quantity,
            'unit_price': order_item.unit_price,
            'unit_cost': unit_cost,
            'revenue': revenue,
            'total_cost': total_cost,
            'profit': profit,
            'margin_percent': margin,
            'cost_missing': unit_cost is None,
        },
    )
    return snapshot


def refresh_order_financials(order, allow_locked=False):
    snapshots = []
    for item in order.items.select_related('product').all():
        snapshot = refresh_item_financial_snapshot(item, allow_locked=allow_locked)
        if snapshot:
            snapshots.append(snapshot)
    note = ensure_cafe_note(order)
    if note and not note.is_locked:
        recalculate_note_totals(note)
    return snapshots


def payment_label(order):
    if order.payments.filter(status='approved').exists():
        return 'Pago'
    if order.payments.filter(status='pending').exists():
        return 'Pendente'
    return 'Sem pagamento confirmado'


def recalculate_note_totals(note):
    rows = OrderItemFinancialSnapshot.objects.filter(order_item__order=note.order)
    quantity = 0
    revenue = Decimal('0')
    total_cost = Decimal('0')
    missing_cost = False
    for row in rows:
        quantity += row.quantity
        revenue += row.revenue or 0
        if row.total_cost is None:
            missing_cost = True
        else:
            total_cost += row.total_cost
    revenue = money(revenue)
    total_cost = money(total_cost)
    profit = money(revenue - total_cost) if not missing_cost else Decimal('0.00')
    margin = (profit / revenue * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if revenue and not missing_cost else Decimal('0.00')
    note.quantity_snapshot = quantity
    note.revenue_snapshot = revenue
    note.cost_snapshot = total_cost
    note.profit_snapshot = profit
    note.margin_snapshot = margin
    note.payment_snapshot = payment_label(note.order)
    note.save(update_fields=[
        'quantity_snapshot', 'revenue_snapshot', 'cost_snapshot', 'profit_snapshot',
        'margin_snapshot', 'payment_snapshot', 'updated_at',
    ])
    return note


def sync_note_payment(order):
    """Payment can change after the commercial note is frozen; item values cannot."""
    note = CafeDeliveryNote.objects.filter(order=order).first()
    if not note:
        return None
    label = payment_label(order)
    if note.payment_snapshot != label:
        note.payment_snapshot = label
        note.save(update_fields=['payment_snapshot', 'updated_at'])
    return note


@transaction.atomic
def lock_cafe_note(note, user=None, force=False):
    note = CafeDeliveryNote.objects.select_for_update().select_related('order').get(pk=note.pk)
    if note.status == 'cancelled' or note.locked_at:
        return note
    now = timezone.now()
    if not force and now < note.editable_until:
        return note
    refresh_order_financials(note.order, allow_locked=True)
    note.status = 'locked'
    note.locked_at = now
    note.locked_by = user if getattr(user, 'is_authenticated', False) else None
    recalculate_note_totals(note)
    note.save(update_fields=['status', 'locked_at', 'locked_by', 'updated_at'])
    return note


def maybe_lock_cafe_note(note, user=None, at=None):
    at = at or timezone.now()
    if note.status == 'draft' and note.locked_at is None and at >= note.editable_until:
        return lock_cafe_note(note, user=user, force=True)
    return note


def lock_due_cafe_notes(at=None):
    at = at or timezone.now()
    # Backfill a note first if an older cafe order predates this feature.
    missing = Order.objects.filter(order_type='cafe', delivery_date__isnull=False, cafe_delivery_note__isnull=True).exclude(status='cancelled')
    for order in missing.iterator():
        ensure_cafe_note(order)
    qs = CafeDeliveryNote.objects.filter(status='draft', locked_at__isnull=True, editable_until__lte=at).select_related('order')
    locked = 0
    for note in qs.iterator():
        lock_cafe_note(note, force=True)
        locked += 1
    return locked


def _sales_rows(start, end, cafe=None, order_type=None):
    qs = OrderItemFinancialSnapshot.objects.select_related(
        'order_item__order__customer',
        'order_item__product',
    ).prefetch_related('order_item__order__payments').filter(
        order_item__order__delivery_date__range=(start, end),
    ).exclude(order_item__order__status='cancelled')
    if order_type:
        qs = qs.filter(order_item__order__order_type=order_type)
    if cafe is not None:
        qs = qs.filter(order_item__order__customer=cafe.user)
    return qs.order_by('order_item__order__delivery_date', 'order_item__order_id', 'product_name')


def sales_report(start, end, cafe=None, order_type=None):
    rows = list(_sales_rows(start, end, cafe=cafe, order_type=order_type))
    totals = {
        'items': 0,
        'revenue': Decimal('0'),
        'received_revenue': Decimal('0'),
        'cost': Decimal('0'),
        'profit': Decimal('0'),
        'missing_cost_items': 0,
        'orders': set(),
        'paid_orders': set(),
    }
    by_product = defaultdict(lambda: {'quantity': 0, 'revenue': Decimal('0'), 'cost': Decimal('0'), 'profit': Decimal('0')})
    by_cafe = defaultdict(lambda: {'quantity': 0, 'revenue': Decimal('0'), 'cost': Decimal('0'), 'profit': Decimal('0'), 'orders': set()})
    by_month = defaultdict(lambda: {'quantity': 0, 'revenue': Decimal('0'), 'cost': Decimal('0'), 'profit': Decimal('0')})

    payment_cache = {}
    for row in rows:
        order = row.order_item.order
        is_paid = payment_cache.setdefault(order.pk, order.payments.filter(status='approved').exists())
        totals['items'] += row.quantity
        totals['revenue'] += row.revenue or 0
        totals['orders'].add(order.pk)
        if is_paid:
            totals['paid_orders'].add(order.pk)
            totals['received_revenue'] += row.revenue or 0
        if row.total_cost is None:
            totals['missing_cost_items'] += row.quantity
        else:
            totals['cost'] += row.total_cost
            totals['profit'] += row.profit or 0

        p = by_product[row.product_name]
        p['quantity'] += row.quantity
        p['revenue'] += row.revenue or 0
        if row.total_cost is not None:
            p['cost'] += row.total_cost
            p['profit'] += row.profit or 0

        cafe_account = getattr(order.customer, 'cafe_account', None)
        cafe_name = cafe_account.business_name if cafe_account else (order.customer.get_full_name() or order.customer.username)
        c = by_cafe[cafe_name]
        c['quantity'] += row.quantity
        c['revenue'] += row.revenue or 0
        c['orders'].add(order.pk)
        if row.total_cost is not None:
            c['cost'] += row.total_cost
            c['profit'] += row.profit or 0

        month = order.delivery_date.strftime('%Y-%m') if order.delivery_date else order.created_at.strftime('%Y-%m')
        m = by_month[month]
        m['quantity'] += row.quantity
        m['revenue'] += row.revenue or 0
        if row.total_cost is not None:
            m['cost'] += row.total_cost
            m['profit'] += row.profit or 0

    totals['revenue'] = money(totals['revenue'])
    totals['received_revenue'] = money(totals['received_revenue'])
    totals['accounts_receivable'] = money(totals['revenue'] - totals['received_revenue'])
    totals['cost'] = money(totals['cost'])
    totals['profit'] = money(totals['profit'])
    totals['order_count'] = len(totals.pop('orders'))
    totals['paid_order_count'] = len(totals.pop('paid_orders'))
    totals['ticket_average'] = money(totals['revenue'] / totals['order_count']) if totals['order_count'] else Decimal('0.00')
    totals['margin_percent'] = (totals['profit'] / totals['revenue'] * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if totals['revenue'] and not totals['missing_cost_items'] else None

    def finish(mapping):
        result = []
        for name, values in mapping.items():
            item = {'name': name, **values}
            if isinstance(item.get('orders'), set):
                item['order_count'] = len(item.pop('orders'))
            for key in ('revenue', 'cost', 'profit'):
                if key in item:
                    item[key] = money(item[key])
            item['margin_percent'] = (item['profit'] / item['revenue'] * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if item.get('revenue') else Decimal('0.00')
            result.append(item)
        return result

    return {
        'start': start,
        'end': end,
        'totals': totals,
        'rows': rows,
        'by_product': sorted(finish(by_product), key=lambda x: (-x['revenue'], x['name'])),
        'by_cafe': sorted(finish(by_cafe), key=lambda x: (-x['revenue'], x['name'])),
        'by_month': sorted(finish(by_month), key=lambda x: x['name']),
    }


def business_financial_summary(start, end):
    report = sales_report(start, end)
    expenses_qs = BusinessExpense.objects.filter(date__range=(start, end), payment_status='paid')
    expenses = money(sum((row.amount for row in expenses_qs), Decimal('0')))
    report['expenses'] = expenses
    report['net_after_expenses'] = money(report['totals']['profit'] - expenses)
    report['expense_rows'] = expenses_qs
    return report
