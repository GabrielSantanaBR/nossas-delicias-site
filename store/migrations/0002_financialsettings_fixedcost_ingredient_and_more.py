import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('desired_margin_percent', models.DecimalField(decimal_places=2, default=30, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('95'))])),
                ('payment_fee_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('50'))])),
                ('tax_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('50'))])),
                ('contingency_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('50'))])),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Configuração financeira',
                'verbose_name_plural': 'Configuração financeira',
            },
        ),
        migrations.CreateModel(
            name='FixedCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('category', models.CharField(choices=[('rent', 'Aluguel'), ('utilities', 'Água, luz, gás e internet'), ('payroll', 'Pessoal/pró-labore'), ('software', 'Sistemas e assinaturas'), ('marketing', 'Marketing'), ('logistics', 'Logística'), ('other', 'Outros')], default='other', max_length=20)),
                ('monthly_amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('due_day', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(28)])),
                ('active', models.BooleanField(default=True)),
                ('start_date', models.DateField(default=django.utils.timezone.localdate)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Custo fixo / recorrente',
                'verbose_name_plural': 'Custos fixos / recorrentes',
                'ordering': ['due_day', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Ingredient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=24, unique=True)),
                ('name', models.CharField(max_length=140)),
                ('category', models.CharField(blank=True, max_length=100)),
                ('package_price', models.DecimalField(decimal_places=2, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('package_quantity', models.DecimalField(decimal_places=4, default=1, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.0001'))])),
                ('base_unit', models.CharField(choices=[('g', 'Grama'), ('ml', 'Mililitro'), ('un', 'Unidade'), ('kg', 'Quilograma'), ('l', 'Litro'), ('other', 'Outro')], default='g', max_length=12)),
                ('unit_cost', models.DecimalField(decimal_places=6, default=0, editable=False, max_digits=14)),
                ('supplier', models.CharField(blank=True, max_length=140)),
                ('aliases', models.TextField(blank=True, help_text='Nomes alternativos separados por |.')),
                ('notes', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('minimum_stock', models.DecimalField(decimal_places=4, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('last_price_update', models.DateField(default=django.utils.timezone.localdate)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ingrediente / insumo',
                'verbose_name_plural': 'Ingredientes / insumos',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='IngredientPriceHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('package_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('package_quantity', models.DecimalField(decimal_places=4, max_digits=14)),
                ('unit_cost', models.DecimalField(decimal_places=6, max_digits=14)),
                ('supplier', models.CharField(blank=True, max_length=140)),
                ('source', models.CharField(blank=True, max_length=160)),
                ('effective_date', models.DateField(db_index=True, default=django.utils.timezone.localdate)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ingredient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='store.ingredient')),
            ],
            options={
                'verbose_name': 'Histórico de preço de ingrediente',
                'verbose_name_plural': 'Histórico de preços de ingredientes',
                'ordering': ['-effective_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InventoryMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(choices=[('purchase', 'Compra/entrada'), ('production', 'Consumo em produção'), ('waste', 'Perda/descarte'), ('adjustment', 'Ajuste de estoque'), ('return', 'Devolução/estorno')], max_length=16)),
                ('quantity_delta', models.DecimalField(decimal_places=4, help_text='Entrada positiva; consumo/perda negativo.', max_digits=14)),
                ('unit_cost_snapshot', models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True)),
                ('date', models.DateField(db_index=True, default=django.utils.timezone.localdate)),
                ('reference', models.CharField(blank=True, max_length=120)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ingredient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='store.ingredient')),
            ],
            options={
                'verbose_name': 'Movimentação de estoque',
                'verbose_name_plural': 'Movimentações de estoque',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=40, unique=True)),
                ('name', models.CharField(max_length=180)),
                ('category', models.CharField(blank=True, max_length=100)),
                ('sale_unit', models.CharField(choices=[('unit', 'Unidade'), ('slice', 'Fatia'), ('portion', 'Grama/porção'), ('box', 'Caixa/kit'), ('other', 'Outro')], default='unit', max_length=16)),
                ('yield_quantity', models.DecimalField(decimal_places=3, default=1, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))])),
                ('extra_cost', models.DecimalField(decimal_places=4, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('imported_production_cost', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('active', models.BooleanField(default=True)),
                ('source_reference', models.CharField(blank=True, max_length=160)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recipe', to='store.product')),
            ],
            options={
                'verbose_name': 'Receita / ficha técnica',
                'verbose_name_plural': 'Receitas / fichas técnicas',
                'ordering': ['category', 'code'],
            },
        ),
        migrations.CreateModel(
            name='SpreadsheetImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=180)),
                ('sha256', models.CharField(db_index=True, max_length=64)),
                ('source_version', models.CharField(blank=True, max_length=80)),
                ('status', models.CharField(choices=[('success', 'Concluído'), ('partial', 'Parcial'), ('failed', 'Falhou')], max_length=12)),
                ('ingredients_created', models.PositiveIntegerField(default=0)),
                ('ingredients_updated', models.PositiveIntegerField(default=0)),
                ('recipes_created', models.PositiveIntegerField(default=0)),
                ('recipes_updated', models.PositiveIntegerField(default=0)),
                ('prices_updated', models.PositiveIntegerField(default=0)),
                ('skipped_rows', models.PositiveIntegerField(default=0)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('imported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Importação de planilha',
                'verbose_name_plural': 'Importações de planilha',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RecipeIngredient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_used', models.DecimalField(decimal_places=4, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.0001'))])),
                ('waste_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('100'))])),
                ('notes', models.CharField(blank=True, max_length=220)),
                ('ingredient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recipe_uses', to='store.ingredient')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingredients', to='store.recipe')),
            ],
            options={
                'verbose_name': 'Ingrediente da receita',
                'verbose_name_plural': 'Ingredientes das receitas',
                'ordering': ['recipe', 'ingredient__name'],
                'unique_together': {('recipe', 'ingredient')},
            },
        ),
    ]
