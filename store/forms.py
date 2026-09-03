import re
from datetime import timedelta

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from .models import CakeDesign, CakeOption, CafeAccount, CustomerAddress, CustomerProfile, EventQuote


class CustomerAuthenticationForm(AuthenticationForm):
    """Customer-facing authentication without leaking Django's default wording."""

    username = forms.CharField(
        label='E-mail ou usuário',
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'placeholder': 'voce@email.com ou seu usuário',
            'autocapitalize': 'none',
        }),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'placeholder': 'Sua senha',
        }),
    )
    error_messages = {
        'invalid_login': 'Não encontramos uma conta com esses dados. Confira e tente de novo.',
        'inactive': 'Esta conta está temporariamente indisponível.',
    }

    def clean(self):
        identifier = (self.cleaned_data.get('username') or '').strip()
        # E-mail is unique in the customer flow. Resolve it internally, then let
        # Django authenticate as usual so timing and password checks stay intact.
        if '@' in identifier:
            username = User.objects.filter(email__iexact=identifier).values_list('username', flat=True).first()
            if username:
                self.cleaned_data['username'] = username
        return super().clean()


class RegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=80,
        label='Como podemos te chamar?',
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'placeholder': 'Seu primeiro nome'}),
    )
    last_name = forms.CharField(
        max_length=80,
        required=False,
        label='Sobrenome (opcional)',
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'placeholder': 'Seu sobrenome'}),
    )
    email = forms.EmailField(
        label='Seu melhor e-mail',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'voce@email.com'}),
    )
    username = forms.CharField(
        max_length=150,
        label='Crie seu usuário',
        help_text='Pode usar letras, números e . @ + - _ !',
        validators=[RegexValidator(
            regex=r'^[\w.@+!\-]+$',
            message='Use letras, números e apenas os sinais . @ + - _ !',
        )],
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'placeholder': 'Ex.: GabrielBezerra!!',
            'autocapitalize': 'none',
        }),
    )
    password1 = forms.CharField(
        label='Crie uma senha',
        help_text='Use pelo menos 12 caracteres e evite informações fáceis de adivinhar.',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Crie uma senha segura'}),
    )
    password2 = forms.CharField(
        label='Confirme sua senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Repita a senha'}),
    )
    marketing_opt_in = forms.BooleanField(required=False, label='Quero receber ofertas e novidades')

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
        if value and len(value) < 2:
            raise forms.ValidationError('Informe seu sobrenome ou deixe este campo em branco.')
        return value

    def clean_username(self):
        value = self.cleaned_data['username'].strip()
        if len(value) < 3:
            raise forms.ValidationError('Escolha um usuário com pelo menos 3 caracteres.')
        if User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError('Este usuário já está em uso. Tente outro.')
        return value

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'As senhas não coincidem.')
            return cleaned
        if password1:
            candidate = User(
                username=cleaned.get('username', ''),
                email=cleaned.get('email', ''),
                first_name=cleaned.get('first_name', ''),
                last_name=cleaned.get('last_name', ''),
            )
            try:
                validate_password(password1, candidate)
            except ValidationError as error:
                self.add_error('password1', error)
        return cleaned

    def save(self, commit=True):
        user = User(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )
        user.set_password(self.cleaned_data['password1'])
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


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=80, label='Nome')
    last_name = forms.CharField(max_length=80, label='Sobrenome')
    email = forms.EmailField(label='E-mail')
    phone = forms.CharField(max_length=24, required=False, label='Telefone')
    birth_date = forms.DateField(required=False, label='Data de nascimento', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    marketing_opt_in = forms.BooleanField(required=False, label='Quero receber ofertas e novidades')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email

    def save(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.user)
        self.user.first_name = ' '.join(self.cleaned_data['first_name'].split())
        self.user.last_name = ' '.join(self.cleaned_data['last_name'].split())
        self.user.email = self.cleaned_data['email']
        self.user.save(update_fields=['first_name', 'last_name', 'email'])
        profile.phone = self.cleaned_data.get('phone', '').strip()
        profile.birth_date = self.cleaned_data.get('birth_date')
        profile.marketing_opt_in = self.cleaned_data.get('marketing_opt_in', False)
        profile.save(update_fields=['phone', 'birth_date', 'marketing_opt_in', 'updated_at'])
        return profile


class AddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        fields = ('label', 'zip_code', 'street', 'number', 'complement', 'neighborhood', 'city', 'default')
        labels = {
            'label': 'Nome do endereço', 'zip_code': 'CEP', 'street': 'Rua', 'number': 'Número',
            'complement': 'Complemento', 'neighborhood': 'Bairro', 'city': 'Cidade', 'default': 'Endereço principal',
        }

    def clean_zip_code(self):
        digits = re.sub(r'\D', '', self.cleaned_data['zip_code'])
        if len(digits) != 8:
            raise forms.ValidationError('Informe um CEP com 8 dígitos.')
        return f'{digits[:5]}-{digits[5:]}'


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


class CakeDesignForm(forms.Form):
    dough = forms.ModelChoiceField(queryset=CakeOption.objects.none(), label='Massa')
    primary_filling = forms.ModelChoiceField(queryset=CakeOption.objects.none(), label='Recheio principal')
    secondary_filling = forms.ModelChoiceField(queryset=CakeOption.objects.none(), required=False, label='Segundo recheio')
    complement = forms.ModelChoiceField(queryset=CakeOption.objects.none(), required=False, label='Complemento')
    frosting = forms.ModelChoiceField(queryset=CakeOption.objects.none(), label='Cobertura')
    decoration_style = forms.ChoiceField(choices=CakeDesign.DECORATION_STYLES, label='Estilo da decoração')
    guest_count = forms.IntegerField(min_value=5, max_value=10000, initial=20, label='Quantidade de pessoas')
    occasion = forms.CharField(max_length=120, required=False, label='Ocasião')
    event_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Dia da festa ou entrega')
    address = forms.CharField(max_length=240, label='Local de entrega')
    decoration_notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False, max_length=1200, label='Como imagina a decoração?')
    reference_image = forms.ImageField(required=False, label='Imagem de referência')
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, max_length=1200, label='Observações gerais')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = CakeOption.objects.filter(active=True)
        self.fields['dough'].queryset = active.filter(kind='dough')
        self.fields['primary_filling'].queryset = active.filter(kind='filling')
        self.fields['secondary_filling'].queryset = active.filter(kind='filling')
        self.fields['complement'].queryset = active.filter(kind='complement')
        self.fields['frosting'].queryset = active.filter(kind='frosting')
        self.fields['event_date'].widget.attrs['min'] = (timezone.localdate() + timedelta(days=7)).isoformat()
        self.fields['occasion'].widget.attrs['placeholder'] = 'Ex.: aniversário, casamento, batizado'
        self.fields['address'].widget.attrs['placeholder'] = 'Rua, número, bairro e cidade'
        self.fields['decoration_notes'].widget.attrs['placeholder'] = 'Cores, tema, nome, idade e elementos desejados…'
        self.fields['notes'].widget.attrs['placeholder'] = 'Restrições, horário preferido ou outro detalhe importante…'

    def clean_event_date(self):
        value = self.cleaned_data['event_date']
        minimum = timezone.localdate() + timedelta(days=7)
        if value < minimum:
            raise forms.ValidationError('Bolos personalizados precisam de pelo menos 7 dias de antecedência.')
        if value > timezone.localdate() + timedelta(days=730):
            raise forms.ValidationError('Para datas além de dois anos, fale diretamente com a equipe.')
        return value

    def clean_reference_image(self):
        image = self.cleaned_data.get('reference_image')
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('A imagem de referência deve ter no máximo 5 MB.')
        return image

    def clean(self):
        cleaned = super().clean()
        for field, kind in (
            ('dough', 'dough'), ('primary_filling', 'filling'), ('secondary_filling', 'filling'),
            ('complement', 'complement'), ('frosting', 'frosting'),
        ):
            option = cleaned.get(field)
            if option and (not option.active or option.kind != kind):
                self.add_error(field, 'Esta opção não está disponível para esta etapa.')
        return cleaned
