from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from trading.models import (
    Alert,
    PaperPortfolio,
    PerformanceReport,
    RiskEvent,
    WorkerHeartbeat,
)
from trading.services.alerts_reports import AlertsReportsService


class AlertsReportsServiceTests(TestCase):
    def setUp(self) -> None:
        self.portfolio = PaperPortfolio.objects.create(
            name="alerts portfolio",
            initial_balance=Decimal("100"),
            cash_balance=Decimal("100"),
        )

    def test_alert_generation_is_idempotent(self) -> None:
        RiskEvent.objects.create(
            portfolio=self.portfolio,
            event_type=RiskEvent.EventType.STOP_LOSS,
            symbol="BTCUSDT",
            price=Decimal("90"),
        )
        WorkerHeartbeat.objects.create(
            name="failed-worker",
            status=WorkerHeartbeat.Status.ERROR,
            last_finished_at=timezone.now(),
            last_error="network failure",
        )
        service = AlertsReportsService()

        first = service.generate_alerts()
        second = service.generate_alerts()

        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(Alert.objects.count(), 2)

    def test_daily_and_weekly_reports_are_unique(self) -> None:
        service = AlertsReportsService()

        daily = service.generate_report(PerformanceReport.Period.DAILY)
        duplicate = service.generate_report(PerformanceReport.Period.DAILY)
        weekly = service.generate_report(PerformanceReport.Period.WEEKLY)

        self.assertIsNotNone(daily)
        self.assertIsNone(duplicate)
        self.assertIsNotNone(weekly)
        self.assertEqual(PerformanceReport.objects.count(), 2)
