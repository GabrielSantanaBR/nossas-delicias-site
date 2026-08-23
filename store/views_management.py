from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .financial_models import BusinessExpense
from .management_forms import (
    ExpenseForm,
    FinancialSettingsForm,
    FixedCostForm,
    IngredientForm,
    InventoryMovementForm,
    PriceSimulatorForm,
    RecipeForm,
    RecipeIngredientForm,
    SpreadsheetUploadForm,
)
from .management_models import (
    FinancialSettings,
    FixedCost,
    Ingredient,
    IngredientPriceHistory,
    InventoryMovement,
    Recipe,
    RecipeIngredient,
    SpreadsheetImportBatch,
)
from .management_services import management_dashboard, simulate_price, sync_recipe_product_cost
from .spreadsheet_io import build_management_workbook, import_management_workbook
from .views_finance import _parse_date, _staff_otp_guard


def _period(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from'), today.replace(day=1))
    end = _parse_date(request.GET.get('to'), today)
    if start > end:
        start, end = end, start
    return start, end


@_staff_otp_guard
def management_center(request):
    start, end = _period(request)
    dashboard = management_dashboard(start, end)
    return render(request, 'store/management_center.html', {
        'start': start,
        'end': end,
        'dashboard': dashboard,
        'ingredients': Ingredient.objects.all()[:250],
        'recipes': Recipe.objects.select_related('product').all()[:250],
        'recipe_ingredients': RecipeIngredient.objects.select_related('recipe', 'ingredient').all()[:400],
        'fixed_costs': FixedCost.objects.all()[:100],
        'recent_expenses': BusinessExpense.objects.order_by('-date', '-created_at')[:80],
        'recent_movements': InventoryMovement.objects.select_related('ingredient').order_by('-date', '-created_at')[:100],
        'recent_imports': SpreadsheetImportBatch.objects.select_related('imported_by')[:12],
        'ingredient_form': IngredientForm(),
        'movement_form': InventoryMovementForm(initial={'date': timezone.localdate()}),
        'recipe_form': RecipeForm(),
        'recipe_ingredient_form': RecipeIngredientForm(),
        'fixed_cost_form': FixedCostForm(initial={'start_date': timezone.localdate()}),
        'expense_form': ExpenseForm(initial={'date': timezone.localdate()}),
        'settings_form': FinancialSettingsForm(instance=FinancialSettings.current()),
        'upload_form': SpreadsheetUploadForm(),
    })


@_staff_otp_guard
@require_POST
def ingredient_save(request):
    pk = request.POST.get('id')
    instance = get_object_or_404(Ingredient, pk=pk) if pk else None
    old_price = instance.package_price if instance else None
    old_quantity = instance.package_quantity if instance else None
    form = IngredientForm(request.POST, instance=instance)
    if form.is_valid():
        ingredient = form.save()
        changed = instance is None or old_price != ingredient.package_price or old_quantity != ingredient.package_quantity
        if changed:
            IngredientPriceHistory.objects.create(
                ingredient=ingredient,
                package_price=ingredient.package_price,
                package_quantity=ingredient.package_quantity,
                unit_cost=ingredient.unit_cost,
                supplier=ingredient.supplier,
                source='Central de Gestão',
                effective_date=timezone.localdate(),
            )
        for recipe in Recipe.objects.filter(ingredients__ingredient=ingredient).distinct():
            sync_recipe_product_cost(recipe)
        messages.success(request, f'{ingredient.name} salvo. Custo unitário: R$ {ingredient.unit_cost:.6f}.')
    else:
        messages.error(request, 'Não foi possível salvar o ingrediente: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def inventory_move(request):
    form = InventoryMovementForm(request.POST)
    if form.is_valid():
        movement = form.save(commit=False)
        movement.created_by = request.user
        movement.save()
        messages.success(request, f'Movimentação registrada para {movement.ingredient.name}.')
    else:
        messages.error(request, 'Movimentação inválida: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def recipe_save(request):
    pk = request.POST.get('id')
    instance = get_object_or_404(Recipe, pk=pk) if pk else None
    form = RecipeForm(request.POST, instance=instance)
    if form.is_valid():
        recipe = form.save()
        sync_recipe_product_cost(recipe)
        messages.success(request, f'Ficha técnica {recipe.code} salva. Custo unitário atual: R$ {recipe.unit_cost:.4f}.')
    else:
        messages.error(request, 'Não foi possível salvar a receita: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def recipe_ingredient_save(request):
    form = RecipeIngredientForm(request.POST)
    if form.is_valid():
        row = form.save()
        sync_recipe_product_cost(row.recipe)
        messages.success(request, f'{row.ingredient.name} vinculado a {row.recipe.code}.')
    else:
        messages.error(request, 'Não foi possível adicionar o ingrediente à receita: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def fixed_cost_save(request):
    form = FixedCostForm(request.POST)
    if form.is_valid():
        cost = form.save()
        messages.success(request, f'Custo fixo “{cost.name}” salvo.')
    else:
        messages.error(request, 'Custo fixo inválido: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def expense_save(request):
    form = ExpenseForm(request.POST, request.FILES)
    if form.is_valid():
        expense = form.save(commit=False)
        expense.created_by = request.user
        expense.save()
        messages.success(request, f'Despesa “{expense.description}” registrada.')
    else:
        messages.error(request, 'Despesa inválida: ' + '; '.join(sum(form.errors.values(), [])))
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def financial_settings_save(request):
    settings = FinancialSettings.current()
    form = FinancialSettingsForm(request.POST, instance=settings)
    if form.is_valid():
        form.save()
        messages.success(request, 'Regras de margem, taxas e contingência atualizadas.')
    else:
        messages.error(request, 'Configuração financeira inválida.')
    return redirect('management_center')


@_staff_otp_guard
@require_POST
def spreadsheet_import(request):
    form = SpreadsheetUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Envie uma planilha .xlsx válida de até 10 MB.')
        return redirect('management_center')
    try:
        result = import_management_workbook(form.cleaned_data['file'], user=request.user)
    except Exception:
        messages.error(request, 'A planilha não pôde ser importada. Nenhuma alteração parcial foi mantida.')
        return redirect('management_center')
    warning = f" Avisos: {'; '.join(result['warnings'])}" if result['warnings'] else ''
    messages.success(
        request,
        f"Planilha importada: {result['ingredients_created']} ingredientes criados, "
        f"{result['ingredients_updated']} atualizados, {result['recipes_created']} receitas criadas, "
        f"{result['recipes_updated']} atualizadas e {result['prices_updated']} preços sincronizados.{warning}",
    )
    return redirect('management_center')


@_staff_otp_guard
def management_export_xlsx(request):
    start, end = _period(request)
    stream = build_management_workbook(start, end)
    response = HttpResponse(
        stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="nossas-delicias-gestao-{start}-{end}.xlsx"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@_staff_otp_guard
def pricing_simulator(request):
    form = PriceSimulatorForm(request.POST or None)
    result = None
    if request.method == 'POST' and form.is_valid():
        result = simulate_price(
            form.cleaned_data['recipe'],
            current_price=form.cleaned_data.get('current_price'),
            desired_margin=form.cleaned_data.get('desired_margin'),
            increase_percent=form.cleaned_data.get('increase_percent'),
            quantity=form.cleaned_data.get('quantity'),
        )
    return render(request, 'store/pricing_simulator.html', {'form': form, 'result': result})
