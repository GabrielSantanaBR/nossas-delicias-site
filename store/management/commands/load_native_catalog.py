import json
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from store.financial_models import ProductCostProfile
from store.management_models import Ingredient, Recipe, RecipeIngredient


DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'nossas_delicias_catalog_v4.json'


def decimal(value, default='0'):
    return Decimal(str(default if value in (None, '') else value))


def ingredient_unit(value):
    normalized = str(value or '').strip().lower()
    return normalized if normalized in {'g', 'ml', 'un', 'kg', 'l'} else 'other'


def sale_unit(value):
    normalized = str(value or '').strip().upper()
    return {
        'UNIDADE': 'unit',
        'FATIA': 'slice',
        'GRAMA/PORÇÃO': 'portion',
        'CAIXA/KIT': 'box',
    }.get(normalized, 'other')


def clean_recipe_name(value):
    name = re.sub(r'^\s*CUSTO\s+DE\s+PRODUÇÃO\s*(?:DE|DO|DA)?\s*/?\s*', '', str(value or ''), flags=re.I)
    name = re.sub(r'\s+R\$\s*\d+(?:[,.]\d+)?\s*$', '', name, flags=re.I).strip(' /-')
    if name and sum(char.isupper() for char in name) > sum(char.islower() for char in name):
        name = name.lower().title()
    return name or str(value or '').strip()


class Command(BaseCommand):
    help = 'Carrega a base nativa de ingredientes e fichas técnicas da Nossas Delícias de forma idempotente.'

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        counters = {'ingredients': 0, 'recipes': 0, 'lines': 0, 'linked': 0}

        ingredients = {}
        for source in data['ingredients']:
            ingredient, created = Ingredient.objects.get_or_create(
                code=source['code'],
                defaults={
                    'name': source['name'][:140],
                    'category': source['category'][:100],
                    'package_price': decimal(source['package_price']),
                    'package_quantity': max(decimal(source['package_quantity'], '1'), Decimal('0.0001')),
                    'base_unit': ingredient_unit(source['base_unit']),
                    'supplier': source['supplier'][:140],
                    'aliases': source['aliases'],
                    'notes': source['notes'],
                    'active': bool(source['active']),
                },
            )
            ingredients[ingredient.code] = ingredient
            counters['ingredients'] += int(created)

        for source in data['recipes']:
            profile = ProductCostProfile.objects.select_related('product').filter(sku=source['code']).first()
            source_name = source['name']
            recipe, created = Recipe.objects.get_or_create(
                code=source['code'],
                defaults={
                    'name': clean_recipe_name(source_name)[:180],
                    'category': source['category'][:100],
                    'sale_unit': sale_unit(source['sale_unit']),
                    'yield_quantity': max(decimal(source['yield_quantity'], '1'), Decimal('0.001')),
                    'imported_production_cost': decimal(source['production_cost']),
                    'product': profile.product if profile else None,
                    'active': bool(source['active']),
                    'source_reference': f'Base nativa 4.0 · {source["code"]}'[:160],
                    'notes': (
                        f'Nome original: {source_name}. '
                        + ('Receita antiga sem quantidades; revisar antes de vender.' if not source.get('ingredients') else 'Composição conferida com a planilha 4.0.')
                    ),
                },
            )
            counters['recipes'] += int(created)
            if profile and not recipe.product_id:
                recipe.product = profile.product
                recipe.save(update_fields=['product', 'updated_at'])
                counters['linked'] += 1

            if recipe.ingredients.exists():
                continue
            consolidated = {}
            for line in source.get('ingredients') or []:
                code = line.get('ingredient_code')
                if code in consolidated:
                    consolidated[code]['quantity_used'] = decimal(consolidated[code]['quantity_used']) + decimal(line['quantity_used'])
                else:
                    consolidated[code] = dict(line)
            for line in consolidated.values():
                ingredient = ingredients.get(line.get('ingredient_code'))
                if not ingredient:
                    continue
                _, line_created = RecipeIngredient.objects.get_or_create(
                    recipe=recipe,
                    ingredient=ingredient,
                    defaults={
                        'quantity_used': decimal(line['quantity_used']),
                        'notes': f'Origem 4.0: {line["ingredient_name"]}'[:220],
                    },
                )
                counters['lines'] += int(line_created)

        self.stdout.write(self.style.SUCCESS(
            'Base nativa pronta: '
            f'{counters["ingredients"]} ingredientes novos, {counters["recipes"]} receitas novas, '
            f'{counters["lines"]} linhas de composição e {counters["linked"]} vínculo(s) com produtos.'
        ))
