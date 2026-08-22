from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import DeliveryRegion, DeliveryRoute, DeliverySlot, Order, Product, ProductPrice


def home(request):
    customer_type = "retail"
    if request.user.is_authenticated and hasattr(request.user, "customer_profile"):
        customer_type = request.user.customer_profile.customer_type

    products = Product.objects.filter(active=True).select_related("category").prefetch_related(
        Prefetch("prices", queryset=ProductPrice.objects.filter(active=True, customer_type=customer_type))
    )[:12]
    regions = DeliveryRegion.objects.filter(active=True)[:12]
    return render(request, "store/home.html", {"products": products, "regions": regions, "customer_type": customer_type})


@login_required
def account(request):
    orders = request.user.orders.select_related("delivery_region", "delivery_slot").order_by("-created_at")
    return render(request, "store/account.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        request.user.orders.prefetch_related("items__product", "status_history", "conversation__messages__sender"),
        pk=pk,
    )
    return render(request, "store/order_detail.html", {"order": order})


def delivery_availability(request):
    region_id = request.GET.get("region")
    region = get_object_or_404(DeliveryRegion, pk=region_id, active=True)
    routes = DeliveryRoute.objects.filter(active=True, regions=region)
    today = timezone.localdate()
    horizon = today + timedelta(days=35)
    slots = DeliverySlot.objects.filter(route__in=routes, date__gte=today, date__lte=horizon, blocked=False).select_related("route")

    # Also expose regular route weekdays even before explicit slot overrides exist.
    regular_dates = []
    current = today
    while current <= horizon:
        for route in routes:
            if current.weekday() == route.weekday:
                regular_dates.append({"date": current, "route": route})
        current += timedelta(days=1)

    return render(request, "store/_availability.html", {"region": region, "slots": slots, "regular_dates": regular_dates})
