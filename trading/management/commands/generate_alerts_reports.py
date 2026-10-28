from django.core.management.base import BaseCommand

from trading.services.alerts_reports import AlertsReportsService


class Command(BaseCommand):
    help = "Generate idempotent in-app alerts and daily/weekly performance reports."

    def handle(self, *args: object, **options: object) -> None:
        alerts, reports = AlertsReportsService().run()
        self.stdout.write(
            self.style.SUCCESS(f"alerts_created={alerts} reports_created={reports}")
        )
