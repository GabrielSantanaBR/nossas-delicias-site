from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Monta a demonstração completa da Nossas Delícias em um único comando.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=timezone.localdate().year)
        parser.add_argument('--demo-password', default='')
        parser.add_argument('--admin-password', default='')
        parser.add_argument('--future-days', type=int, default=75)

    def handle(self, *args, **options):
        call_command(
            'seed_nossas_delicias_demo',
            year=options['year'],
            demo_password=options['demo_password'],
            admin_password=options['admin_password'],
        )
        call_command(
            'seed_nossas_delicias_calendar',
            year=options['year'],
            future_days=options['future_days'],
        )
        self.stdout.write(self.style.SUCCESS('Demonstração completa pronta.'))
