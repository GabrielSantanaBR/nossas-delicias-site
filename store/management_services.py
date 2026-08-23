from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from django.db.models import Q, Sum
from django.utils import timezone

from .financial_models import BusinessExpense, ProductCostProfile
from .financial_services import business_financial_summary, money, sales_report
from .management_models import FinancialSettings, FixedCost, Ingredient, Recipe
from .models import Order, Payment, ProductPrice

CENT = Decimal('0.01')
HUNDRED = Decimal('100')


def month_keys(start, end):
    cursor = start.replace(day=1)
    finish = end.replace(day=1)
    while cursor <= finish:
        yield cursor.year, cursor.month
        cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)


def channel_price(product, kind):
    if not product:
        return None
    row = ProductPrice.objects.filter(product=product, table__active=True, table__kind=kind).order_by('min_quantity', '-updated_at').first()
    return row.unit_price if row else None


def sync_recipe_product_cost(recipe):
    if not recipe.product_id:
        return None
    profile, _ = ProductCostProfile.objects.get_or_create(
        product=recipe.product,
        defaults={
            'sku': recipe.code,
            'sale_unit': recipe.sale_unit,
            'yield_quantity': recipe.yield_quantity,
            'production_cost': recipe.production_cost,
            'source_reference': recipe.source_reference or 'Central de Gestão',
            'active': recipe.active,
        },
    )
    profile.sku = recipe.code
    profile.sale_unit = recipe.sale_unit
    profile.yield_quantity = recipe.yield_quantity
    profile.production_cost = recipe.production_cost
    profile.source_reference = recipe.source_reference or 'Central de Gestão'
    profile.active = recipe.active
    profile.save()
    return profile


def pricing_rows():
    settings = FinancialSettings.current()
    rows = []
    for recipe in Recipe.objects.select_related('product').prefetch_related('ingredients__ingredient').all():
        unit_cost = recipe.unit_cost
        cafe_price = channel_price(recipe.product, 'cafe')
        client_price = channel_price(recipe.product, 'retail')
        recommended = settings.recommended_price(unit_cost)

        def metrics(price):
            if price is None:
                return None, None
            profit = (Decimal(price) - unit_cost).quantize(CENT, rounding=ROUND_HALF_UP)
            margin = (profit / Decimal(price) * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if price else Decimal('0')
            return profit, margin

        cafe_profit, cafe_margin = metrics(cafe_price)
        client_profit, client_margin = metrics(client_price)
        if not recipe.active:
            status = 'INATIVA'
        elif unit_cost <= 0:
            status = 'REVISAR CUSTO/RENDIMENTO'
        elif not recipe.product_id:
            status = 'SEM PRODUTO VINCULADO'
        elif cafe_price is None or client_price is None:
            status = 'PREENCHER PREÇO'
        elif min(cafe_margin or 0, client_margin or 0) < settings.desired_margin_percent:
            status = 'ABAIXO DA META'
        else:
            status = 'OK'
        rows.append({
            'recipe': recipe,
            'unit_cost': unit_cost,
            'production_cost': recipe.production_cost,
            'cafe_price': cafe_price,
            'client_price': client_price,
            'cafe_profit': cafe_profit,
            'cafe_margin': cafe_margin,
            'client_profit': client_profit,
            'client_margin': client_margin,
            'recommended_price': recommended,
            'status': status,
        })
    return rows


def pricing_health():
    rows = pricing_rows()
    statuses = defaultdict(int)
    for row in rows:
        statuses[row['status']] += 1
    active = [row for row in rows if row['recipe'].active]
    status_map = dict(statuses)
    # Stable aliases are useful in Django templates, where dictionary keys with
    # spaces are intentionally awkward to address.
    status_map['PREENCHER_PREÇO'] = statuses['PREENCHER PREÇO']
    status_map['ABAIXO_DA_META'] = statuses['ABAIXO DA META']
    status_map['REVISAR_CUSTO'] = statuses['REVISAR CUSTO/RENDIMENTO']
    return {
        'rows': rows,
        'active_recipes': len(active),
        'cafe_prices': sum(1 for row in active if row['cafe_price'] is not None),
        'client_prices': sum(1 for row in active if row['client_price'] is not None),
        'desired_margin': FinancialSettings.current().desired_margin_percent,
        'statuses': status_map,
        'ok_count': statuses['OK'],
        'fill_price_count': statuses['PREENCHER PREÇO'],
        'below_target_count': statuses['ABAIXO DA META'],
        'review_cost_count': statuses['REVISAR CUSTO/RENDIMENTO'],
        'unlinked_count': statuses['SEM PRODUTO VINCULADO'],
        'highest_cost': sorted(active, key=lambda row: row['unit_cost'], reverse=True)[:10],
    }


def inventory_overview():
    ingredients = list(Ingredient.objects.filter(active=True).order_by('category', 'name'))
    rows = []
    total_value = Decimal('0')
    low = 0
    for ingredient in ingredients:
        balance = ingredient.stock_balance
        value = (balance * ingredient.unit_cost).quantize(CENT, rounding=ROUND_HALF_UP)
        is_low = bool(ingredient.minimum_stock and balance <= ingredient.minimum_stock)
        if is_low:
            low += 1
        if value > 0:
            total_value += value
        rows.append({'ingredient': ingredient, 'balance': balance, 'value': value, 'is_low': is_low})
    return {'rows': rows, 'low_count': low, 'stock_value': money(total_value)}


def fixed_cost_forecast(start, end):
    costs = FixedCost.objects.filter(active=True, start_date__lte=end).filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
    total = Decimal('0')
    rows = []
    for cost in costs:
        months = 0
        for year, month in month_keys(start, end):
            month_start = date(year, month, 1)
            if month_start < cost.start_date.replace(day=1):
                continue
            if cost.end_date and month_start > cost.end_date.replace(day=1):
                continue
            months += 1
        amount = Decimal(cost.monthly_amount) * months
        total += amount
        rows.append({'cost': cost, 'months': months, 'forecast': money(amount)})
    return {'rows': rows, 'total': money(total)}


def active_monthly_fixed_cost():
    today = timezone.localdate()
    queryset = FixedCost.objects.filter(active=True, start_date__lte=today).filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
    return money(queryset.aggregate(total=Sum('monthly_amount'))['total'] or 0)


def receivables_report(start, end):
    orders = Order.objects.filter(
        Q(delivery_date__range=(start, end)) | Q(delivery_date__isnull=True, created_at__date__range=(start, end))
    ).exclude(status='cancelled').select_related('customer').prefetch_related('payments')
    rows = []
    total = Decimal('0')
    overdue = Decimal('0')
    today = timezone.localdate()
    for order in orders:
        approved = sum((p.amount for p in order.payments.all() if p.status == 'approved'), Decimal('0'))
        due = max(Decimal(order.total or 0) - approved, Decimal('0'))
        if due <= 0:
            continue
        is_overdue = bool(order.delivery_date and order.delivery_date < today)
        total += due
        if is_overdue:
            overdue += due
        cafe = getattr(order.customer, 'cafe_account', None)
        rows.append({
            'order': order,
            'customer_name': cafe.business_name if cafe else (order.customer.get_full_name() or order.customer.username),
            'due': money(due),
            'overdue': is_overdue,
        })
    rows.sort(key=lambda row: (not row['overdue'], row['order'].delivery_date or today, row['customer_name']))
    return {'rows': rows, 'total': money(total), 'overdue': money(overdue)}


def payables_report(start, end):
    rows = list(BusinessExpense.objects.filter(date__range=(start, end), payment_status='pending').order_by('date', 'description'))
    total = money(sum((row.amount for row in rows), Decimal('0')))
    return {'rows': rows, 'total': total}


def cashflow_summary(start, end):
    payments = Payment.objects.filter(status='approved', paid_at__date__range=(start, end))
    cash_in = money(payments.aggregate(total=Sum('amount'))['total'] or 0)
    paid_expenses = BusinessExpense.objects.filter(date__range=(start, end), payment_status='paid')
    cash_out = money(paid_expenses.aggregate(total=Sum('amount'))['total'] or 0)
    receivables = receivables_report(start, end)
    payables = payables_report(start, end)
    fixed = fixed_cost_forecast(start, end)
    return {
        'cash_in': cash_in,
        'cash_out': cash_out,
        'net_cash': money(cash_in - cash_out),
        'receivables': receivables,
        'payables': payables,
        'fixed_cost_forecast': fixed,
    }


def break_even_for_period(start, end):
    report = business_financial_summary(start, end)
    fixed = fixed_cost_forecast(start, end)['total']
    revenue = report['totals']['revenue']
    profit = report['totals']['profit']
    missing_cost = report['totals']['missing_cost_items']
    if revenue > 0 and not missing_cost and profit > 0:
        contribution_margin = profit / revenue
    else:
        contribution_margin = FinancialSettings.current().desired_margin_percent / HUNDRED
    break_even_revenue = money(fixed / contribution_margin) if contribution_margin > 0 else None
    gap = money(max((break_even_revenue or Decimal('0')) - revenue, Decimal('0'))) if break_even_revenue is not None else None
    progress = min((revenue / break_even_revenue * HUNDRED), Decimal('999.99')).quantize(CENT, rounding=ROUND_HALF_UP) if break_even_revenue else None
    return {
        'fixed_cost': fixed,
        'contribution_margin_percent': (contribution_margin * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP),
        'break_even_revenue': break_even_revenue,
        'current_revenue': revenue,
        'gap': gap,
        'progress_percent': progress,
    }


def management_dashboard(start, end):
    financial = business_financial_summary(start, end)
    cashflow = cashflow_summary(start, end)
    pricing = pricing_health()
    inventory = inventory_overview()
    cafe = sales_report(start, end, order_type='cafe')
    retail = sales_report(start, end, order_type='retail')
    event = sales_report(start, end, order_type='event')
    return {
        'financial': financial,
        'cashflow': cashflow,
        'pricing': pricing,
        'inventory': inventory,
        'break_even': break_even_for_period(start, end),
        'cafe': cafe,
        'retail': retail,
        'event': event,
    }


def simulate_price(recipe, current_price=None, desired_margin=None, increase_percent=None, quantity=1):
    settings = FinancialSettings.current()
    unit_cost = recipe.unit_cost
    recommended = settings.recommended_price(unit_cost, desired_margin=desired_margin)
    current = Decimal(current_price) if current_price not in (None, '') else None
    increase = Decimal(increase_percent or 0) / Decimal('100')
    new_price = (current * (Decimal('1') + increase)).quantize(CENT, rounding=ROUND_HALF_UP) if current is not None else recommended

    def profit(price):
        return (Decimal(price) - unit_cost).quantize(CENT, rounding=ROUND_HALF_UP) if price is not None else None

    current_profit = profit(current)
    new_profit = profit(new_price)
    margin = (new_profit / new_price * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if new_price and new_profit is not None else None
    extra_per_unit = (new_profit - current_profit).quantize(CENT, rounding=ROUND_HALF_UP) if current_profit is not None and new_profit is not None else None
    extra_total = (extra_per_unit * Decimal(quantity or 1)).quantize(CENT, rounding=ROUND_HALF_UP) if extra_per_unit is not None else None
    fixed_monthly = active_monthly_fixed_cost()
    break_even_units = ceil(fixed_monthly / new_profit) if fixed_monthly > 0 and new_profit and new_profit > 0 else None
    break_even_revenue = money(Decimal(break_even_units) * new_price) if break_even_units is not None and new_price is not None else None
    return {
        'recipe': recipe,
        'unit_cost': unit_cost,
        'current_price': current,
        'new_price': new_price,
        'recommended_price': recommended,
        'current_profit': current_profit,
        'new_profit': new_profit,
        'new_margin': margin,
        'extra_per_unit': extra_per_unit,
        'extra_total': extra_total,
        'quantity': quantity,
        'fixed_monthly': fixed_monthly,
        'break_even_units': break_even_units,
        'break_even_revenue': break_even_revenue,
    }
