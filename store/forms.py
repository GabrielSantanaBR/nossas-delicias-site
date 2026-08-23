import re
from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import CafeAccount, EventQuote


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label='E-mail')
    first_name = forms.CharField(max_length=80, label='Nome')
    last_name = forms.CharField(max_length=80, label='Sobrenome')
    marketing_opt_in = forms.BooleanField(required=False, label='Quero receber ofertas e novidades')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password1', 'password2')
        labels = {'username': 'Usuário'}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean_first_name(self):
        value = ' '.join(self.cleaned_data['first_name'].split()).strip()
        if len(value) < 2:
            raise forms.ValidationError('Informe seu nome.')
        return value

    def clean_last_name(self):
        value = ' '.join(self.cleaned_data['last_name'].split()).strip()
        if len(value) < 2:
            raise forms.ValidationError('Informe seu sobrenome.')
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class CheckoutForm(forms.Form):
    zip_code = forms.CharField(max_length=10, label='CEP')
    delivery_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Data de entrega')
    address = forms.CharField(max_length=240, label='Endereço completo')
    note = forms.CharField(widget=forms.Textarea, required=False, max_length=1000, label='Observações')
    promotion_code = forms.CharField(required=False, max_length=40, label='Cupom')
    save_address = forms.BooleanField(required=False, label='Salvar este endereço')

    def clean_zip_code(self):
        digits = re.sub(r'\D', '', self.cleaned_data['zip_code'])
        if len(digits) != 8:
            raise forms.ValidationError('Informe um CEP com 8 dígitos.')
        return f'{digits[:5]}-{digits[5:]}'

    def clean_delivery_date(self):
        value = self.cleaned_data['delivery_date']
        if value < timezone.localdate():
            raise forms.ValidationError('A data de entrega não pode estar no passado.')
        if value > timezone.localdate() + timedelta(days=180):
            raise forms.ValidationError('Escolha uma data dentro dos próximos 180 dias.')
        return value

    def clean_address(self):
        value = ' '.join(self.cleaned_data['address'].split()).strip()
        if len(value) < 8:
            raise forms.ValidationError('Informe um endereço mais completo.')
        return value

    def clean_promotion_code(self):
        return (self.cleaned_data.get('promotion_code') or '').strip().upper()


class CafeApplicationForm(forms.ModelForm):
    phone = forms.CharField(max_length=24, required=False, label='Telefone de contato')

    class Meta:
        model = CafeAccount
        fields = ('business_name', 'contact_name', 'document')
        labels = {
            'business_name': 'Nome da cafeteria',
            'contact_name': 'Responsável',
            'document': 'CNPJ/CPF (opcional)',
        }

    def clean_business_name(self):
        value = ' '.join(self.cleaned_data['business_name'].split()).strip()
        if len(value) < 2:
            raise forms.ValidationError('Informe o nome da cafeteria.')
        return value

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        if value and len(re.sub(r'\D', '', value)) < 10:
            raise forms.ValidationError('Informe um telefone válido com DDD.')
        return value

    def save_for_user(self, user):
        account = self.save(commit=False)
        account.user = user
        account.approved = False
        account.save()
        profile = user.customer_profile
        profile.phone = self.cleaned_data.get('phone', '')
        profile.save(update_fields=['phone', 'updated_at'])
        return account


class EventQuoteForm(forms.ModelForm):
    class Meta:
        model = EventQuote
        fields = ('event_type', 'event_date', 'guest_count', 'address', 'notes')
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {
            'event_type': 'Tipo de evento',
            'event_date': 'Data',
            'guest_count': 'Número de pessoas',
            'address': 'Local do evento',
            'notes': 'O que você está imaginando?',
        }

    def clean_event_date(self):
        value = self.cleaned_data['event_date']
        if value < timezone.localdate():
            raise forms.ValidationError('A data do evento não pode estar no passado.')
        if value > timezone.localdate() + timedelta(days=730):
            raise forms.ValidationError('Para datas além de dois anos, fale diretamente com a equipe.')
        return value

    def clean_guest_count(self):
        value = self.cleaned_data['guest_count']
        if value > 10000:
            raise forms.ValidationError('Para eventos acima de 10.000 pessoas, fale diretamente com a equipe.')
        return value
