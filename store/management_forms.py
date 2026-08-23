from decimal import Decimal

from django import forms

from .financial_models import BusinessExpense
from .management_models import FinancialSettings, FixedCost, Ingredient, InventoryMovement, Recipe, RecipeIngredient


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
