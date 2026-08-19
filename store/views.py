import json
from datetime import date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit
from .forms import CafeApplicationForm, CheckoutForm, EventQuoteForm, RegisterForm
from .models import CafeAccount, Cart, CartItem, Category, Conversation, CustomerAddress, CustomerProfile, Order, Payment, Product, PromotionRedemption
from .payment_gateway import create_checkout_preference, fetch_payment, validate_webhook
from .services import available_dates, can_schedule, cart_snapshot, customer_order_type, discount_for, eligible_promotions, product_allowed, promotion_for_code, region_for_zip


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
            user=form.save(); CustomerProfile.objects.create(user=user,marketing_opt_in=form.cleaned_data.get('marketing_opt_in',False)); Cart.objects.create(user=user)
        login(request,user); return redirect('account')
    return render(request,'registration/register.html',{'form':form})


@login_required
def account(request):
    profile,_=CustomerProfile.objects.get_or_create(user=request.user)
    orders=request.user.orders.prefetch_related('items__product','payments').order_by('-created_at')
    return render(request,'store/account.html',{'profile':profile,'orders':orders,'promotions':eligible_promotions(request.user),'event_quotes':request.user.event_quotes.order_by('-created_at')[:10]})


@login_required
@require_POST
@ratelimit(key='user',rate='40/m',method='POST',block=True)
def add_to_cart(request):
    try:
        product=get_object_or_404(Product,id=int(request.POST.get('product_id')),active=True)
        quantity=max(product.min_quantity,int(request.POST.get('quantity','1')))
    except (TypeError,ValueError): return JsonResponse({'error':'Produto ou quantidade inválidos.'},status=400)
    order_type=customer_order_type(request.user)
    if not product_allowed(product,order_type): return JsonResponse({'error':'Este produto não está disponível para o seu perfil.'},status=403)
    cart,_=Cart.objects.get_or_create(user=request.user)
    item,created=CartItem.objects.get_or_create(cart=cart,product=product,defaults={'quantity':quantity})
    if not created:
        item.quantity=min(item.quantity+quantity,9999); item.save(update_fields=['quantity','updated_at'])
    return JsonResponse({'ok':True,'count':sum(i.quantity for i in cart.items.all()),'redirect':'/carrinho/'})


@login_required
@require_POST
def update_cart_item(request,item_id):
    cart,_=Cart.objects.get_or_create(user=request.user); item=get_object_or_404(CartItem,id=item_id,cart=cart)
    try: quantity=int(request.POST.get('quantity','1'))
    except ValueError: quantity=1
    if quantity<=0: item.delete()
    else:
        item.quantity=max(item.product.min_quantity,min(quantity,9999)); item.note=request.POST.get('note','')[:250]; item.save(update_fields=['quantity','note','updated_at'])
    return redirect('cart')


@login_required
@require_POST
def remove_cart_item(request,item_id):
    cart,_=Cart.objects.get_or_create(user=request.user); get_object_or_404(CartItem,id=item_id,cart=cart).delete(); return redirect('cart')


@login_required
def cart_view(request):
    snapshot=cart_snapshot(request.user)
    form=CheckoutForm()
    return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)})


@login_required
@require_GET
@ratelimit(key='user',rate='60/m',method='GET',block=True)
def delivery_availability(request):
    region=region_for_zip(request.GET.get('cep',''))
    if not region: return JsonResponse({'available':False,'error':'Região ainda não atendida.'},status=404)
    snapshot=cart_snapshot(request.user)
    lead=snapshot['max_lead'] if snapshot['rows'] else 1
    dates=available_dates(region,lead_days=lead)
    return JsonResponse({'available':bool(dates),'region':region.name,'fee':float(region.delivery_fee),'minimum_order':float(region.minimum_order),'dates':[{'date':d['date'].isoformat(),'remaining':d['remaining'],'start':d['start_time'].strftime('%H:%M'),'end':d['end_time'].strftime('%H:%M')} for d in dates]})


@login_required
@require_POST
@ratelimit(key='user',rate='10/m',method='POST',block=True)
def checkout_cart(request):
    form=CheckoutForm(request.POST)
    snapshot=cart_snapshot(request.user)
    if not form.is_valid() or not snapshot['rows']:
        return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)},status=400)
    region=region_for_zip(form.cleaned_data['zip_code'])
    if not region:
        form.add_error('zip_code','Ainda não entregamos nesta região.'); return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)},status=422)
    chosen=form.cleaned_data['delivery_date']
    if not can_schedule(region,chosen,snapshot['max_lead']):
        form.add_error('delivery_date','Esta data não está mais disponível.'); return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)},status=409)
    minimum=region.minimum_order
    cafe=getattr(request.user,'cafe_account',None)
    if snapshot['order_type']=='cafe' and cafe and cafe.approved: minimum=max(minimum,cafe.minimum_order)
    if snapshot['subtotal']<minimum:
        form.add_error(None,f'Pedido mínimo para este perfil/região: R$ {minimum:.2f}'); return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)},status=422)
    promotion=promotion_for_code(request.user,form.cleaned_data.get('promotion_code'))
    discount=discount_for(promotion,snapshot['subtotal'])
    with transaction.atomic():
        # Re-check availability inside the atomic section immediately before reserving the slot.
        if not can_schedule(region,chosen,snapshot['max_lead']):
            form.add_error('delivery_date','A última vaga desta data acabou de ser ocupada.'); return render(request,'store/cart.html',{'snapshot':snapshot,'form':form,'addresses':request.user.saved_addresses.all(),'promotions':eligible_promotions(request.user)},status=409)
        order=Order.objects.create(customer=request.user,order_type=snapshot['order_type'],status='pending_payment',delivery_date=chosen,delivery_region=region,delivery_address=form.cleaned_data['address'][:1000],delivery_fee=region.delivery_fee,subtotal=snapshot['subtotal'],discount=discount,total=snapshot['subtotal']-discount+region.delivery_fee,promotion_code=promotion.code if promotion else '',customer_note=form.cleaned_data['note'][:1000])
        for row in snapshot['rows']:
            order.items.create(product=row['product'],quantity=row['quantity'],unit_price=row['unit_price'],note=row['item'].note)
        Conversation.objects.create(order=order,customer=request.user)
        order.status_history.create(status='pending_payment',changed_by=request.user,note='Pedido criado.')
        if promotion: PromotionRedemption.objects.create(promotion=promotion,user=request.user,order=order,discount_amount=discount)
        snapshot['cart'].items.all().delete()
        if form.cleaned_data.get('save_address'):
            CustomerAddress.objects.get_or_create(user=request.user,zip_code=form.cleaned_data['zip_code'],street=form.cleaned_data['address'][:180],number='s/n',defaults={'label':'Entrega'})
    return redirect('order_detail',public_id=order.public_id)


@login_required
def order_detail(request,public_id):
    order=get_object_or_404(Order.objects.prefetch_related('items__product','status_history','payments'),public_id=public_id,customer=request.user)
    conversation,_=Conversation.objects.get_or_create(order=order,defaults={'customer':request.user})
    return render(request,'store/order_detail.html',{'order':order,'conversation':conversation})


@login_required
def cafe_portal(request):
    account=CafeAccount.objects.filter(user=request.user).first()
    form=None if account else CafeApplicationForm()
    recurring=account.recurring_orders.prefetch_related('items__product') if account and account.approved else []
    return render(request,'store/cafe.html',{'account':account,'form':form,'recurring':recurring})


@login_required
@require_POST
@ratelimit(key='user',rate='3/d',method='POST',block=True)
def cafe_apply(request):
    if CafeAccount.objects.filter(user=request.user).exists(): return redirect('cafe_portal')
    form=CafeApplicationForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            form.save_for_user(request.user)
            profile,_=CustomerProfile.objects.get_or_create(user=request.user); profile.customer_type='cafe'; profile.save(update_fields=['customer_type','updated_at'])
        messages.success(request,'Cadastro de cafeteria enviado para aprovação.')
        return redirect('cafe_portal')
    return render(request,'store/cafe.html',{'form':form,'account':None},status=400)


@login_required
def event_portal(request):
    form=EventQuoteForm(); quotes=request.user.event_quotes.prefetch_related('items').order_by('-created_at')
    return render(request,'store/events.html',{'form':form,'quotes':quotes})


@login_required
@require_POST
@ratelimit(key='user',rate='8/d',method='POST',block=True)
def event_quote_create(request):
    form=EventQuoteForm(request.POST)
    if form.is_valid():
        quote=form.save(commit=False); quote.customer=request.user; quote.save(); messages.success(request,'Pedido de orçamento recebido. Você poderá acompanhar pela sua conta.'); return redirect('event_portal')
    return render(request,'store/events.html',{'form':form,'quotes':request.user.event_quotes.all()},status=400)


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
    reference=remote.get('external_reference'); order=Order.objects.filter(public_id=reference).first()
    if not order: return HttpResponse(status=200)
    mapped={'approved':'approved','pending':'pending','in_process':'pending','rejected':'rejected','refunded':'refunded','cancelled':'cancelled'}.get(remote.get('status'),'pending')
    with transaction.atomic():
        payment,_=Payment.objects.get_or_create(order=order,provider='mercado_pago',provider_id=provider_id,defaults={'amount':order.total})
        payment.status=mapped; payment.method=str(remote.get('payment_type_id') or remote.get('payment_method_id') or '')[:30]; payment.raw_reference={'payment_id':provider_id,'status':str(remote.get('status',''))[:40]}
        if mapped=='approved': payment.paid_at=timezone.now()
        payment.save()
        if mapped=='approved' and order.status=='pending_payment':
            order.status='paid'; order.save(update_fields=['status','updated_at']); order.status_history.create(status='paid',note='Pagamento confirmado pelo Mercado Pago.')
    return HttpResponse(status=200)
