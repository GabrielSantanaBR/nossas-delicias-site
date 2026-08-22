from django.core.management.base import BaseCommand
from django.utils import timezone

from store.financial_services import lock_due_cafe_notes


class Command(BaseCommand):
    help = 'Fecha notas de cafeteria que já atingiram o corte de 16h do dia da entrega.'

    def handle(self, *args, **options):
        count = lock_due_cafe_notes()
        self.stdout.write(self.style.SUCCESS(
            f'{count} nota(s) fechada(s) em {timezone.localtime():%d/%m/%Y %H:%M}.'
        ))
