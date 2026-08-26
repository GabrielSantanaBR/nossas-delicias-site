from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import AvailabilityDay


class Command(BaseCommand):
    help = 'Preenche o calendário de disponibilidade da demonstração Nossas Delícias.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=timezone.localdate().year)
        parser.add_argument('--future-days', type=int, default=75)

    def handle(self, *args, **options):
        year = options['year']
        august_start = date(year, 8, 1)
        future_end = timezone.localdate() + timedelta(days=max(options['future_days'], 0))
        august_end = date(year, 8, 31)
        end = max(august_end, future_end)

        current = august_start
        created = updated = 0
        while current <= end:
            enabled = current.weekday() != 6  # Domingo fechado para clientes; rotas B2B continuam mais restritas.
            note = (
                'DEMO · Clientes: Nilópolis/Zona Oeste, máximo 5 pedidos/dia e 7 dias de antecedência. '
                'Cafeterias: Centro/Zona Sul somente terça, quinta e sexta.'
            )
            _, was_created = AvailabilityDay.objects.update_or_create(
                date=current,
                defaults={
                    'enabled': enabled,
                    # O teto de clientes é aplicado separadamente em services.py.
                    # 24 mantém espaço para a operação B2B sem aumentar o limite retail.
                    'capacity': 24 if enabled else 0,
                    'note': note,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f'Calendário demo preenchido: {created} novas datas, {updated} atualizadas.'
        ))
