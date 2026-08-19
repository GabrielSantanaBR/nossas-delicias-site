from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
from .models import CustomerProfile, Order

@receiver(post_save,sender=Order)
def refresh_customer_metrics(sender,instance,**kwargs):
    if instance.status!='completed': return
    profile,_=CustomerProfile.objects.get_or_create(user=instance.customer)
    completed=instance.customer.orders.filter(status='completed')
    profile.orders_count=completed.count()
    profile.lifetime_value=completed.aggregate(total=Sum('total'))['total'] or 0
    profile.save(update_fields=['orders_count','lifetime_value','updated_at'])
