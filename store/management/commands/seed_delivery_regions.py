from decimal import Decimal
from django.core.management.base import BaseCommand
from store.models import DeliveryRegion


REGIONS = [
    ("Nova Iguaçu", "Nova Iguaçu", "Centro, Moquetá, Jardim Tropical, Posse", "12.00", "45.00"),
    ("Mesquita", "Mesquita", "Centro, Edson Passos, Chatuba, Banco de Areia", "11.00", "40.00"),
    ("Nilópolis", "Nilópolis", "Centro, Olinda, Cabuís, Nova Cidade", "10.00", "35.00"),
    ("São João de Meriti", "São João de Meriti", "Centro, Vilar dos Teles, Coelho da Rocha, Jardim Meriti", "10.00", "35.00"),
    ("Guadalupe e Anchieta", "Rio de Janeiro", "Guadalupe, Anchieta, Parque Anchieta, Ricardo de Albuquerque", "8.00", "30.00"),
    ("Deodoro e Vila Militar", "Rio de Janeiro", "Deodoro, Vila Militar, Magalhães Bastos, Realengo", "9.00", "35.00"),
    ("Bangu e Padre Miguel", "Rio de Janeiro", "Bangu, Padre Miguel, Senador Camará", "10.00", "35.00"),
    ("Madureira e entorno", "Rio de Janeiro", "Madureira, Campinho, Oswaldo Cruz, Cascadura, Praça Seca", "11.00", "40.00"),
    ("Méier e Grande Tijuca", "Rio de Janeiro", "Méier, Engenho de Dentro, Tijuca, Maracanã, Vila Isabel", "14.00", "50.00"),
    ("Centro", "Rio de Janeiro", "Centro, Lapa, Santa Teresa, Cidade Nova", "16.00", "55.00"),
    ("Zona Sul 1", "Rio de Janeiro", "Flamengo, Catete, Glória, Botafogo, Laranjeiras, Cosme Velho", "18.00", "60.00"),
    ("Zona Sul 2", "Rio de Janeiro", "Copacabana, Leme, Ipanema, Leblon, Lagoa, Jardim Botânico, Gávea", "22.00", "70.00"),
]


class Command(BaseCommand):
    help = "Cria uma base EDITÁVEL de regiões entre Nova Iguaçu e Zona Sul. Taxas são iniciais e devem ser revisadas pelo administrador."

    def handle(self, *args, **options):
        for position, (name, city, neighborhoods, fee, minimum) in enumerate(REGIONS, start=1):
            region, created = DeliveryRegion.objects.update_or_create(
                name=name,
                defaults={
                    "city": city,
                    "neighborhoods": neighborhoods,
                    "delivery_fee": Decimal(fee),
                    "minimum_order": Decimal(minimum),
                    "active": True,
                    "position": position,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"{'Criada' if created else 'Atualizada'}: {region}"))

        self.stdout.write(self.style.WARNING("Revise taxas, bairros e CEPs no painel /controle-interno/ antes de abrir pedidos reais."))
