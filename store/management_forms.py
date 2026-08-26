from decimal import Decimal

from django import forms
from django.contrib.auth.models import User

from .financial_models import BusinessExpense
from .management_models import FinancialSettings, FixedCost, Ingredient, InventoryMovement, Recipe, RecipeIngredient
from .models import Category, Order, Product


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ('code', 'name', 'category', 'package_price', 'package_quantity', 'base_unit', 'supplier', 'aliases', 'minimum_stock', 'active', 'notes')


class InventoryMovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ('ingredient', 'movement_type', 'quantity_delta', 'date', 'reference', 'notes')
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ('code', 'name', 'category', 'sale_unit', 'yield_quantity', 'extra_cost', 'imported_production_cost', 'product', 'active', 'notes')


class RecipeIngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ('recipe', 'ingredient', 'quantity_used', 'waste_percent', 'notes')


class FixedCostForm(forms.ModelForm):
    class Meta:
        model = FixedCost
        fields = ('name', 'category', 'monthly_amount', 'due_day', 'active', 'start_date', 'end_date', 'notes')
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = BusinessExpense
        fields = ('date', 'category', 'description', 'supplier', 'amount', 'payment_status', 'payment_method', 'attachment', 'notes')
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class FinancialSettingsForm(forms.ModelForm):
    class Meta:
        model = FinancialSettings
        fields = ('desired_margin_percent', 'payment_fee_percent', 'tax_percent', 'contingency_percent')


class SpreadsheetUploadForm(forms.Form):
    file = forms.FileField(label='Planilha .xlsx')

    def clean_file(self):
        upload = self.cleaned_data['file']
        name = upload.name.lower()
        if not name.endswith('.xlsx'):
            raise forms.ValidationError('Envie uma planilha .xlsx.')
        if upload.size > 10 * 1024 * 1024:
            raise forms.ValidationError('A planilha deve ter no máximo 10 MB.')
        return upload


class PriceSimulatorForm(forms.Form):
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.filter(active=True), label='Receita')
    current_price = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal('0.01'), label='Preço atual')
    desired_margin = forms.DecimalField(max_digits=6, decimal_places=2, required=False, min_value=Decimal('0'), max_value=Decimal('95'), label='Margem desejada (%)')
    increase_percent = forms.DecimalField(max_digits=6, decimal_places=2, required=False, min_value=Decimal('-90'), max_value=Decimal('500'), initial=10, label='Aumento (%)')
    quantity = forms.IntegerField(min_value=1, max_value=100000, initial=100, label='Quantidade projetada')


class CatalogProductForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.none(), required=False, label='Produto existente (opcional)')
    category = forms.ModelChoiceField(queryset=Category.objects.none(), label='Categoria')
    name = forms.CharField(max_length=140, label='Nome do produto')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), max_length=2000, label='Descrição')
    image = forms.ImageField(required=False, label='Foto própria (opcional)')
    active = forms.BooleanField(required=False, initial=True, label='Publicado')
    featured = forms.BooleanField(required=False, label='Destaque na página inicial')
    sell_retail = forms.BooleanField(required=False, initial=True, label='Cliente final')
    sell_cafe = forms.BooleanField(required=False, label='Cafeterias')
    sell_event = forms.BooleanField(required=False, initial=True, label='Eventos')
    min_quantity = forms.IntegerField(min_value=1, max_value=100000, initial=1, label='Quantidade mínima')
    lead_time_days = forms.IntegerField(min_value=0, max_value=365, initial=3, label='Antecedência em dias')
    stock_limit = forms.IntegerField(min_value=0, max_value=1000000, required=False, label='Limite disponível')
    sku = forms.CharField(max_length=40, required=False, label='Código/SKU')
    sale_unit = forms.ChoiceField(choices=Recipe.SALE_UNITS, initial='unit', label='Unidade de venda')
    production_cost = forms.DecimalField(min_value=Decimal('0'), max_digits=12, decimal_places=4, required=False, label='Custo total do lote')
    yield_quantity = forms.DecimalField(min_value=Decimal('0.001'), max_digits=12, decimal_places=3, initial=1, label='Rendimento do lote')
    retail_price = forms.DecimalField(min_value=Decimal('0.01'), max_digits=10, decimal_places=2, required=False, label='Preço cliente')
    cafe_price = forms.DecimalField(min_value=Decimal('0.01'), max_digits=10, decimal_places=2, required=False, label='Preço cafeteria')
    event_price = forms.DecimalField(min_value=Decimal('0.01'), max_digits=10, decimal_places=2, required=False, label='Preço evento')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('category').order_by('name')
        self.fields['category'].queryset = Category.objects.filter(active=True).order_by('sort_order', 'name')

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('A foto deve ter no máximo 5 MB.')
        if image and getattr(image, 'content_type', '') not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise forms.ValidationError('Use uma imagem JPG, PNG ou WebP.')
        return image

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(field) for field in ('sell_retail', 'sell_cafe', 'sell_event')):
            raise forms.ValidationError('Escolha pelo menos um canal de venda.')
        if cleaned.get('sell_retail') and not cleaned.get('retail_price'):
            self.add_error('retail_price', 'Informe o preço para cliente final.')
        if cleaned.get('sell_cafe') and not cleaned.get('cafe_price'):
            self.add_error('cafe_price', 'Informe o preço para cafeteria.')
        return cleaned


class DirectSaleForm(forms.Form):
    PAYMENT_STATUSES = [('approved', 'Recebido'), ('pending', 'A receber')]
    PAYMENT_METHODS = [('pix', 'Pix'), ('card', 'Cartão'), ('cash', 'Dinheiro'), ('transfer', 'Transferência'), ('other', 'Outro')]

    customer = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label='Cliente já cadastrado')
    customer_name = forms.CharField(max_length=150, required=False, label='Nome do novo cliente')
    customer_email = forms.EmailField(max_length=254, required=False, label='E-mail do novo cliente')
    order_type = forms.ChoiceField(choices=Order.TYPES, initial='retail', label='Canal')
    product = forms.ModelChoiceField(queryset=Product.objects.none(), label='Produto')
    quantity = forms.IntegerField(min_value=1, max_value=100000, initial=1, label='Quantidade')
    unit_price = forms.DecimalField(min_value=Decimal('0.01'), max_digits=10, decimal_places=2, required=False, label='Preço unitário (opcional)')
    sale_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Data da venda')
    payment_status = forms.ChoiceField(choices=PAYMENT_STATUSES, initial='approved', label='Pagamento')
    payment_method = forms.ChoiceField(choices=PAYMENT_METHODS, initial='pix', label='Forma de pagamento')
    note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), max_length=1000, required=False, label='Observações')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = User.objects.filter(is_active=True, is_staff=False).order_by('first_name', 'username')
        self.fields['product'].queryset = Product.objects.filter(active=True).select_related('category').order_by('category__sort_order', 'sort_order', 'name')

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('customer'):
            if not (cleaned.get('customer_name') or '').strip():
                self.add_error('customer_name', 'Informe o nome do novo cliente.')
            if not cleaned.get('customer_email'):
                self.add_error('customer_email', 'Informe o e-mail do novo cliente.')
        return cleaned
