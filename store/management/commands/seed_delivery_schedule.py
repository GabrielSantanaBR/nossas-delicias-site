from datetime import time
from django.core.management.base import BaseCommand
from store.models import DeliveryRegion, DeliveryRoute


class Command(BaseCommand):
    help = "Cria duas janelas semanais iniciais de entrega, totalmente editáveis no painel."

    def handle(self, *args, **options):
        west_names = [
            "Nova Iguaçu", "Mesquita", "Nilópolis", "São João de Meriti",
            "Guadalupe e Anchieta", "Deodoro e Vila Militar", "Bangu e Padre Miguel",
        ]
        city_names = [
            "Madureira e entorno", "Méier e Grande Tijuca", "Centro", "Zona Sul 1", "Zona Sul 2",
        ]

        west = DeliveryRegion.objects.filter(name__in=west_names, active=True)
        city = DeliveryRegion.objects.filter(name__in=city_names, active=True)

        for weekday in (1, 3):  # terça e quinta
            route, _ = DeliveryRoute.objects.update_or_create(
                name=f"Baixada e Zona Oeste - {weekday}",
                defaults={
                    "weekday": weekday,
                    "start_time": time(10, 0),
                    "end_time": time(18, 0),
                    "max_orders": 30,
                    "max_capacity_units": 300,
                    "active": True,
                },
            )
            route.regions.set(west)

        for weekday in (2, 5):  # quarta e sábado
            route, _ = DeliveryRoute.objects.update_or_create(
                name=f"Centro e Zona Sul - {weekday}",
                defaults={
                    "weekday": weekday,
                    "start_time": time(10, 0),
                    "end_time": time(19, 0),
                    "max_orders": 24,
                    "max_capacity_units": 250,
                    "active": True,
                },
            )
            route.regions.set(city)

        self.stdout.write(self.style.SUCCESS("Rotas iniciais criadas. Edite dias, horários, capacidade e regiões no painel."))
