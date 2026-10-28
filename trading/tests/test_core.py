from django.test import TestCase
from django.urls import reverse

from trading.models import Strategy, WorkerHeartbeat


class HealthViewTests(TestCase):
    def test_health_endpoint_uses_paper_mode(self):
        response = self.client.get(reverse("trading:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["trading_mode"], "paper")

    def test_readiness_requires_and_accepts_recent_healthy_workers(self):
        unavailable = self.client.get(reverse("trading:ready"))
        self.assertEqual(unavailable.status_code, 503)
        WorkerHeartbeat.objects.create(
            name="paper-trading-worker",
            status=WorkerHeartbeat.Status.HEALTHY,
            last_success_at=timezone.now(),
        )

        available = self.client.get(reverse("trading:ready"))

        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.json()["status"], "ready")


class StrategyModelTests(TestCase):
    def test_strategy_string(self):
        strategy = Strategy(name="Moving Average", symbol="BTC/USDT")

        self.assertEqual(str(strategy), "Moving Average (BTC/USDT)")


from django.utils import timezone
