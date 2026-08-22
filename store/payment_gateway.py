import uuid
import mercadopago
from django.conf import settings
from django.urls import reverse
from mercadopago.config import RequestOptions
from mercadopago.webhook import WebhookSignatureValidator, InvalidWebhookSignatureError


def sdk():
    if not settings.MERCADO_PAGO_ACCESS_TOKEN:
        raise RuntimeError('MERCADO_PAGO_ACCESS_TOKEN não configurado.')
    return mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)


def create_checkout_preference(request, order):
    base=f'{request.scheme}://{request.get_host()}'
    items=[{'id':str(item.product_id),'title':item.product.name[:120],'quantity':item.quantity,'currency_id':'BRL','unit_price':float(item.unit_price)} for item in order.items.select_related('product')]
    if order.delivery_fee:
        items.append({'id':'delivery','title':f'Entrega - {order.delivery_region.name if order.delivery_region else "Taxa"}','quantity':1,'currency_id':'BRL','unit_price':float(order.delivery_fee)})
    preference={
        'items':items,
        'payer':{'email':order.customer.email,'name':order.customer.first_name,'surname':order.customer.last_name},
        'external_reference':str(order.public_id),
        'back_urls':{
            'success':base+reverse('payment_return')+'?result=success',
            'pending':base+reverse('payment_return')+'?result=pending',
            'failure':base+reverse('payment_return')+'?result=failure',
        },
        'auto_return':'approved',
        'notification_url':base+reverse('mp_webhook'),
        'statement_descriptor':'NOSSAS DELICIAS',
    }
    options=RequestOptions(); options.custom_headers={'x-idempotency-key':str(order.public_id)}
    result=sdk().preference().create(preference,options)
    if result.get('status') not in (200,201):
        raise RuntimeError('Falha ao criar checkout no provedor.')
    return result['response']


def validate_webhook(request):
    if not settings.MERCADO_PAGO_WEBHOOK_SECRET:
        return False
    try:
        WebhookSignatureValidator.validate(
            request.headers.get('x-signature'),
            request.headers.get('x-request-id'),
            request.GET.get('data.id'),
            settings.MERCADO_PAGO_WEBHOOK_SECRET,
        )
        return True
    except InvalidWebhookSignatureError:
        return False


def fetch_payment(payment_id):
    result=sdk().payment().get(payment_id)
    if result.get('status') != 200:
        raise RuntimeError('Não foi possível confirmar o pagamento no provedor.')
    return result['response']
