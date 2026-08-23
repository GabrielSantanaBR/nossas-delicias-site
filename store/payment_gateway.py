import uuid
from decimal import Decimal

import mercadopago
from django.conf import settings
from django.urls import reverse
from mercadopago.config import RequestOptions
from mercadopago.webhook import WebhookSignatureValidator, InvalidWebhookSignatureError


def sdk():
    if not settings.MERCADO_PAGO_ACCESS_TOKEN:
        raise RuntimeError('MERCADO_PAGO_ACCESS_TOKEN não configurado.')
    return mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)


def _public_base_url(request):
    configured = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
    if configured:
        return configured
    return f'{request.scheme}://{request.get_host()}'


def _idempotency_key(order):
    # A preference must change when an editable order changes, but repeated clicks
    # for the same order revision must remain idempotent.
    seed = f'{order.public_id}:{order.updated_at.isoformat()}:{order.total}'
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def create_checkout_preference(request, order):
    if order.total is None or Decimal(order.total) <= 0:
        raise RuntimeError('O pedido não possui um total válido para pagamento.')
    if not order.items.exists():
        raise RuntimeError('O pedido não possui itens para pagamento.')

    base = _public_base_url(request)
    # Use the authoritative order total as the checkout amount. Sending every
    # line separately would re-create the subtotal and could ignore discounts.
    # The complete item breakdown remains stored in our own order database.
    preference = {
        'items': [{
            'id': str(order.public_id),
            'title': f'Pedido Nossas Delícias #{str(order.public_id)[:8].upper()}',
            'description': f'{order.items.count()} item(ns) + entrega/descontos já calculados',
            'quantity': 1,
            'currency_id': 'BRL',
            'unit_price': float(order.total),
        }],
        'payer': {
            'email': order.customer.email,
            'name': order.customer.first_name,
            'surname': order.customer.last_name,
        },
        'external_reference': str(order.public_id),
        'back_urls': {
            'success': base + reverse('payment_return') + '?result=success',
            'pending': base + reverse('payment_return') + '?result=pending',
            'failure': base + reverse('payment_return') + '?result=failure',
        },
        'auto_return': 'approved',
        'notification_url': base + reverse('mp_webhook'),
        'statement_descriptor': 'NOSSAS DELICIAS',
        'metadata': {
            'order_id': str(order.public_id),
            'order_type': order.order_type,
        },
    }
    options = RequestOptions()
    options.custom_headers = {'x-idempotency-key': _idempotency_key(order)}
    result = sdk().preference().create(preference, options)
    if result.get('status') not in (200, 201):
        raise RuntimeError('Falha ao criar checkout no provedor.')
    response = result.get('response') or {}
    if not response.get('id') or not response.get('init_point'):
        raise RuntimeError('O provedor retornou um checkout incompleto.')
    return response


def validate_webhook(request):
    if not settings.MERCADO_PAGO_WEBHOOK_SECRET:
        return False
    signature = request.headers.get('x-signature')
    request_id = request.headers.get('x-request-id')
    data_id = request.GET.get('data.id')
    if not signature or not request_id or not data_id:
        return False
    try:
        WebhookSignatureValidator.validate(
            signature,
            request_id,
            data_id,
            settings.MERCADO_PAGO_WEBHOOK_SECRET,
        )
        return True
    except (InvalidWebhookSignatureError, ValueError, TypeError):
        return False


def fetch_payment(payment_id):
    if not str(payment_id).isdigit():
        raise RuntimeError('Identificador de pagamento inválido.')
    result = sdk().payment().get(str(payment_id))
    if result.get('status') != 200:
        raise RuntimeError('Não foi possível confirmar o pagamento no provedor.')
    response = result.get('response') or {}
    if not response.get('id'):
        raise RuntimeError('Resposta de pagamento inválida.')
    return response
