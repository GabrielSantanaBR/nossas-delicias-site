import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from .forms import RegisterForm
from .models import Category, Conversation, CustomerProfile, Order, Payment, Product
from .services import eligible_promotions, price_for, region_for_zip


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
@require_POST
@ratelimit(key='user',rate='20/m',method='POST',block=True)
def create_order(request):
    data=request.POST
    try: product=get_object_or_404(Product,id=int(data.get('product_id')),active=True); quantity=max(product.min_quantity,int(data.get('quantity','1')))
    except (TypeError,ValueError): return JsonResponse({'error':'Produto ou quantidade inválidos.'},status=400)
    profile,_=CustomerProfile.objects.get_or_create(user=request.user); order_type=profile.customer_type if profile.customer_type in {'retail','cafe','event'} else 'retail'
    unit_price=price_for(request.user,product,quantity,order_type)
    if unit_price is None: return JsonResponse({'error':'Preço indisponível para este produto.'},status=409)
    zip_code=data.get('zip_code',''); region=region_for_zip(zip_code)
    if not region: return JsonResponse({'error':'Ainda não entregamos neste CEP. Consulte retirada ou atendimento.'},status=422)
    subtotal=unit_price*quantity
    if subtotal < region.minimum_order: return JsonResponse({'error':f'Pedido mínimo para {region.name}: R$ {region.minimum_order:.2f}'},status=422)
    with transaction.atomic():
        order=Order.objects.create(customer=request.user,order_type=order_type,status='pending_payment',delivery_region=region,delivery_address=data.get('address','')[:1000],delivery_fee=region.delivery_fee,subtotal=subtotal,total=subtotal+region.delivery_fee,customer_note=data.get('note','')[:1000])
        order.items.create(product=product,quantity=quantity,unit_price=unit_price,note=data.get('item_note','')[:250])
        Conversation.objects.create(order=order,customer=request.user)
    return JsonResponse({'order_id':str(order.public_id),'redirect':f'/pedidos/{order.public_id}/'})


@csrf_exempt
@require_POST
def mercado_pago_webhook(request):
    # Signature verification is delegated to the official SDK adapter before production activation.
    try: payload=json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError: return HttpResponse(status=400)
    provider_id=str((payload.get('data') or {}).get('id') or request.GET.get('data.id') or '')[:160]
    if not provider_id: return HttpResponse(status=400)
    # Webhook is acknowledged but no order state is trusted from body alone. A server-to-server
    # authenticated fetch must confirm payment status before mutating Payment/Order.
    return HttpResponse(status=200)
