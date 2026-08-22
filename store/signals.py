from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import CustomerProfile, Order, OrderItem
from .financial_models import OrderItemFinancialSnapshot
from .financial_services import ensure_cafe_note, recalculate_note_totals, refresh_item_financial_snapshot


@receiver(post_save, sender=Order)
def refresh_customer_metrics(sender, instance, **kwargs):
    if instance.status == 'completed':
        profile, _ = CustomerProfile.objects.get_or_create(user=instance.customer)
        completed = instance.customer.orders.filter(status='completed')
        profile.orders_count = completed.count()
        profile.lifetime_value = completed.aggregate(total=Sum('total'))['total'] or 0
        profile.save(update_fields=['orders_count', 'lifetime_value', 'updated_at'])

    if instance.order_type == 'cafe' and instance.delivery_date:
        ensure_cafe_note(instance)


@receiver(post_save, sender=OrderItem)
def refresh_order_item_financials(sender, instance, **kwargs):
    snapshot = refresh_item_financial_snapshot(instance)
    if instance.order.order_type == 'cafe':
        note = ensure_cafe_note(instance.order)
        if note and not note.is_locked and snapshot:
            recalculate_note_totals(note)


@receiver(post_delete, sender=OrderItem)
def refresh_note_after_item_delete(sender, instance, **kwargs):
    OrderItemFinancialSnapshot.objects.filter(order_item_id=instance.pk).delete()
    if instance.order.order_type == 'cafe':
        note = ensure_cafe_note(instance.order)
        if note and not note.is_locked:
            recalculate_note_totals(note)
