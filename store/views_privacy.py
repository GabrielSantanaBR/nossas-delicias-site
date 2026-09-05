from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import PrivacyRequestForm
from .models import DataSubjectRequest, EventQuote, Order
from .privacy import set_consent


def privacy_notice(request):
    return render(request, 'store/privacy_notice.html', {
        'request_form': PrivacyRequestForm(user=request.user),
    })


@require_POST
@ratelimit(key='ip', rate='30/h', method='POST', block=True)
def privacy_cookie_preferences(request):
    raw_choice = request.POST.get('analytics')
    if raw_choice not in {'0', '1'}:
        return HttpResponseBadRequest('Preferência de cookies inválida.')
    analytics = raw_choice == '1'
    response = JsonResponse({'analytics': analytics, 'state': 'granted' if analytics else 'denied'})
    set_consent(response, analytics)
    return response


@require_POST
@ratelimit(key='ip', rate='5/d', method='POST', block=True)
def privacy_request_create(request):
    form = PrivacyRequestForm(request.POST, user=request.user)
    if not form.is_valid():
        return render(request, 'store/privacy_notice.html', {'request_form': form}, status=400)

    data = form.cleaned_data
    open_request = DataSubjectRequest.objects.filter(
        email=data['email'],
        request_type=data['request_type'],
        status__in={'new', 'review', 'waiting'},
        created_at__gte=timezone.now() - timedelta(days=1),
    ).exists()
    if open_request:
        messages.info(request, 'Já existe uma solicitação semelhante em análise. Não é necessário enviar outra agora.')
    else:
        DataSubjectRequest.objects.create(
            requester=request.user if request.user.is_authenticated else None,
            email=data['email'],
            request_type=data['request_type'],
            details=data['details'],
        )
        messages.success(request, 'Sua solicitação foi registrada. A equipe fará a validação de identidade antes de compartilhar ou alterar dados.')
    return redirect(f'{reverse("privacy_notice")}#solicitacao')


@login_required
@require_POST
@never_cache
@ratelimit(key='user', rate='2/d', method='POST', block=True)
def privacy_export(request):
    """Provide a minimal self-service copy without payment-provider payloads."""
    user = request.user
    orders = Order.objects.filter(customer=user).prefetch_related('items__product', 'payments')
    quotes = EventQuote.objects.filter(customer=user).prefetch_related('items__product', 'messages__sender')
    conversations = user.conversations.prefetch_related('messages__sender', 'order')
    payload = {
        'generated_at': timezone.now().isoformat(),
        'profile': {
            'name': user.get_full_name(),
            'username': user.username,
            'email': user.email,
            'phone': getattr(getattr(user, 'customer_profile', None), 'phone', ''),
            'marketing_opt_in': getattr(getattr(user, 'customer_profile', None), 'marketing_opt_in', False),
        },
        'addresses': [{
            'label': address.label,
            'zip_code': address.zip_code,
            'street': address.street,
            'number': address.number,
            'complement': address.complement,
            'neighborhood': address.neighborhood,
            'city': address.city,
        } for address in user.saved_addresses.all()],
        'orders': [{
            'id': str(order.public_id),
            'status': order.status,
            'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
            'delivery_address': order.delivery_address,
            'total': str(order.total),
            'items': [{'product': line.product.name, 'quantity': line.quantity, 'unit_price': str(line.unit_price)} for line in order.items.all()],
            'payments': [{'provider': payment.provider, 'status': payment.status, 'amount': str(payment.amount), 'method': payment.method} for payment in order.payments.all()],
        } for order in orders],
        'event_quotes': [{
            'id': str(quote.public_id),
            'event_date': quote.event_date.isoformat(),
            'guest_count': quote.guest_count,
            'address': quote.address,
            'status': quote.status,
            'items': [{'description': item.description, 'quantity': item.quantity} for item in quote.items.all()],
            'messages': [{'from_team': message.sender.is_staff, 'body': message.body, 'created_at': message.created_at.isoformat()} for message in quote.messages.all()],
        } for quote in quotes],
        'order_messages': [{
            'order_id': str(conversation.order.public_id),
            'messages': [{'from_team': message.sender.is_staff, 'body': message.body, 'created_at': message.created_at.isoformat()} for message in conversation.messages.all()],
        } for conversation in conversations],
    }
    response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = 'attachment; filename="nossas-delicias-meus-dados.json"'
    return response
