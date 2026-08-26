from datetime import date

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import AvailabilityDay


class DemoCalendarTests(TestCase):
    def test_calendar_fills_august_and_keeps_sundays_closed(self):
        year = timezone.localdate().year
        call_command('seed_nossas_delicias_calendar', year=year, future_days=0, verbosity=0)
        august = AvailabilityDay.objects.filter(date__year=year, date__month=8)
        self.assertEqual(august.count(), 31)
        for row in august:
            if row.date.weekday() == 6:
                self.assertFalse(row.enabled)
                self.assertEqual(row.capacity, 0)
            else:
                self.assertTrue(row.enabled)
                self.assertEqual(row.capacity, 24)
        self.assertTrue(AvailabilityDay.objects.filter(date=date(year, 8, 1)).exists())
