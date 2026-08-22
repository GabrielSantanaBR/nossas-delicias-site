from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CafeAccount, EventQuote

class RegisterForm(UserCreationForm):
    email=forms.EmailField(required=True)
    first_name=forms.CharField(max_length=80)
    last_name=forms.CharField(max_length=80)
    marketing_opt_in=forms.BooleanField(required=False,label='Quero receber ofertas e novidades')
    class Meta:
        model=User
        fields=('first_name','last_name','email','username','password1','password2')
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email
    def save(self,commit=True):
        user=super().save(commit=False)
        user.email=self.cleaned_data['email']; user.first_name=self.cleaned_data['first_name']; user.last_name=self.cleaned_data['last_name']
        if commit: user.save()
        return user

class CheckoutForm(forms.Form):
    zip_code=forms.CharField(max_length=10,label='CEP')
    delivery_date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}),label='Data de entrega')
    address=forms.CharField(max_length=240,label='Endereço')
    note=forms.CharField(widget=forms.Textarea,required=False,max_length=1000,label='Observações')
    promotion_code=forms.CharField(required=False,max_length=40,label='Cupom')
    save_address=forms.BooleanField(required=False,label='Salvar este endereço')

class CafeApplicationForm(forms.ModelForm):
    phone=forms.CharField(max_length=24,required=False,label='Telefone de contato')
    class Meta:
        model=CafeAccount
        fields=('business_name','contact_name','document')
        labels={'business_name':'Nome da cafeteria','contact_name':'Responsável','document':'CNPJ/CPF (opcional)'}
    def save_for_user(self,user):
        account=self.save(commit=False); account.user=user; account.approved=False; account.save()
        profile=user.customer_profile
        profile.phone=self.cleaned_data.get('phone',''); profile.save(update_fields=['phone','updated_at'])
        return account

class EventQuoteForm(forms.ModelForm):
    class Meta:
        model=EventQuote
        fields=('event_type','event_date','guest_count','address','notes')
        widgets={'event_date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':5})}
        labels={'event_type':'Tipo de evento','event_date':'Data','guest_count':'Número de pessoas','address':'Local do evento','notes':'O que você está imaginando?'}
