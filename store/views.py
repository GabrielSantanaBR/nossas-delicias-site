import json
from datetime import date
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit
from .forms import RegisterForm
from .models import Category, Conversation, CustomerProfile, Order, Payment, Product
from .payment_gateway import create_checkout_preference, fetch_payment, validate_webhook
from .services import available_dates, can_schedule, eligible_promotions, price_for, region_for_zip


def home(request):
    categories=Category.objects.filter(active=True).prefetch_related('products')
    featured=Product.objects.filter(active=True,featured=True).select_related('category')[:8]
    return render(request,'store/home.html',{'categories':categories,'featured':featured})


def catalog(request):
    categories=Category.objects.filter(active=True).prefetch_related('products__prices')
    return render(request,'store/catalog.html',{'categories':categories})


@ratelimit(key='ip',rate='5/m',method='POST',block=True)
def register(request):
    if request.user.is_authenticated: return redirect('account')
    form=RegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            user=form.save(); CustomerProfile.objects.create(user=user,marketing_opt_in=form.cleaned_data.get('marketing_opt_in',False))
        login(request,user); return redirect('account')
    return render(request,'registration/register.html',{'form':form})


@login_required
def account(request):
    profile,_=CustomerProfile.objects.get_or_create(user=request.user)
    orders=request.user.orders.prefetch_related('items__product','payments').order_by('-created_at')
    return render(request,'store/account.html',{'profile':profile,'orders':orders,'promotions':eligible_promotions(request.user)})


@login_required
def order_detail(request,public_id):
    order=get_object_or_404(Order.objects.prefetch_related('items__product','status_history','payments'),public_id=public_id,customer=request.user)
    conversation,_=Conversation.objects.get_or_create(order=order,defaults={'customer':request.user})
    return render(request,'store/order_detail.html',{'order':order,'conversation':conversation})


@login_required
@require_GET
@ratelimit(key='user',rate='60/m',method='GET',block=True)
def delivery_availability(request):
    region=region_for_zip(request.GET.get('cep',''))
    if not region: return JsonResponse({'available':False,'error':'Região ainda não atendida.'},status=404)
    try: lead=max(1,min(int(request.GET.get('antecedencia','1')),60))
    except ValueError: lead=1
    dates=available_dates(region,lead_days=lead)
    return JsonResponse({'available':bool(dates),'region':region.name,'fee':float(region.delivery_fee),'minimum_order':float(region.minimum_order),'dates':[{'date':d['date'].isoformat(),'remaining':d['remaining'],'start':d['start_time'].strftime('%H:%M'),'end':d['end_time'].strftime('%H:%M')} for d in dates]})


@login_required
@require_POST
@ratelimit(key='user',rate='20/m',method='POST',block=True)
def create_order(request):
    data=request.POST
    try:
        product=get_object_or_404(Product,id=int(data.get('product_id')),active=True)
        quantity=max(product.min_quantity,int(data.get('quantity','1')))
        delivery_date=date.fromisoformat(data.get('delivery_date',''))
    except (TypeError,ValueError):
        return JsonResponse({'error':'Produto, quantidade ou data inválidos.'},status=400)
    profile,_=CustomerProfile.objects.get_or_create(user=request.user)
    order_type=profile.customer_type if profile.customer_type in {'retail','cafe','event'} else 'retail'
    unit_price=price_for(request.user,product,quantity,order_type)
    if unit_price is None: return JsonResponse({'error':'Preço indisponível para este produto.'},status=409)
    region=region_for_zip(data.get('zip_code',''))
    if not region: return JsonResponse({'error':'Ainda não entregamos neste CEP. Consulte retirada ou atendimento.'},status=422)
    if not can_schedule(region,delivery_date,product.lead_time_days): return JsonResponse({'error':'Esta data não está mais disponível para sua região ou produto.'},status=409)
    subtotal=unit_price*quantity
    if subtotal < region.minimum_order: return JsonResponse({'error':f'Pedido mínimo para {region.name}: R$ {region.minimum_order:.2f}'},status=422)
    with transaction.atomic():
        order=Order.objects.create(customer=request.user,order_type=order_type,status='pending_payment',delivery_date=delivery_date,delivery_region=region,delivery_address=data.get('address','')[:1000],delivery_fee=region.delivery_fee,subtotal=subtotal,total=subtotal+region.delivery_fee,customer_note=data.get('note','')[:1000])
        order.items.create(product=product,quantity=quantity,unit_price=unit_price,note=data.get('item_note','')[:250])
        Conversation.objects.create(order=order,customer=request.user)
    return JsonResponse({'order_id':str(order.public_id),'redirect':f'/pedidos/{order.public_id}/'})


@login_required
@require_POST
@ratelimit(key='user',rate='10/m',method='POST',block=True)
def start_payment(request,public_id):
    order=get_object_or_404(Order.objects.prefetch_related('items__product'),public_id=public_id,customer=request.user,status='pending_payment')
    try: preference=create_checkout_preference(request,order)
    except RuntimeError as exc: return JsonResponse({'error':str(exc)},status=503)
    Payment.objects.get_or_create(order=order,provider='mercado_pago',provider_id=str(preference.get('id','')),defaults={'status':'pending','amount':order.total,'method':'checkout_pro','raw_reference':{'preference_id':str(preference.get('id',''))[:160]}})
    url=preference.get('init_point')
    if not url: return JsonResponse({'error':'Checkout indisponível.'},status=503)
    return JsonResponse({'checkout_url':url})


@login_required
def payment_return(request):
    reference=request.GET.get('external_reference')
    if reference:
        order=Order.objects.filter(public_id=reference,customer=request.user).first()
        if order: return redirect('order_detail',public_id=order.public_id)
    return redirect('account')


@csrf_exempt
@require_POST
@ratelimit(key='ip',rate='120/m',method='POST',block=True)
def mercado_pago_webhook(request):
    if not validate_webhook(request): return HttpResponse(status=401)
    try: payload=json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError: return HttpResponse(status=400)
    provider_id=str((payload.get('data') or {}).get('id') or request.GET.get('data.id') or '')[:160]
    if not provider_id: return HttpResponse(status=400)
    try: remote=fetch_payment(provider_id)
    except RuntimeError: return HttpResponse(status=503)
    reference=remote.get('external_reference')
    order=Order.objects.filter(public_id=reference).first()
    if not order: return HttpResponse(status=200)
    mapped={'approved':'approved','pending':'pending','in_process':'pending','rejected':'rejected','refunded':'refunded','cancelled':'cancelled'}.get(remote.get('status'),'pending')
    with transaction.atomic():
        payment,_=Payment.objects.get_or_create(order=order,provider='mercado_pago',provider_id=provider_id,defaults={'amount':order.total})
        payment.status=mapped; payment.method=str(remote.get('payment_type_id') or remote.get('payment_method_id') or '')[:30]
        payment.raw_reference={'payment_id':provider_id,'status':str(remote.get('status',''))[:40]}
        if mapped=='approved': payment.paid_at=timezone.now()
        payment.save()
        if mapped=='approved' and order.status=='pending_payment':
            order.status='paid'; order.save(update_fields=['status','updated_at']); order.status_history.create(status='paid',note='Pagamento confirmado pelo provedor.')
    return HttpResponse(status=200)
