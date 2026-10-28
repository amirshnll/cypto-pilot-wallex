from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from decimal import Decimal

from django.utils import timezone

from trading.models import (
    BotConfiguration,
    MarketSnapshot,
    Strategy,
    Trade,
    WorkerHeartbeat,
)
from trading.views import build_market_chart_data


class DashboardTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="operator", password="test-password", is_staff=True
        )

    def test_dashboard_requires_authentication(self) -> None:
        response = self.client.get(reverse("trading:dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_staff_user_can_open_dashboard(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(reverse("trading:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paper trading dashboard")

    def test_settings_encrypt_api_key(self) -> None:
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("trading:settings"),
            {
                "enabled": "on",
                "symbols": ["BTCTMN", "ETHTMN"],
                "initial_tmn_balance": "21330000",
                "risk_level": "medium",
                "fast_period": "5",
                "slow_period": "20",
                "rsi_period": "14",
                "rsi_buy_ceiling": "70",
                "rsi_sell_floor": "70",
                "enabled_strategies": [
                    "sma_rsi",
                    "momentum",
                    "macd",
                    "bollinger",
                    "breakout",
                ],
                "consensus_threshold": "0.35",
                "commodity_fast_period": "5",
                "commodity_slow_period": "20",
                "commodity_rsi_period": "14",
                "commodity_rsi_buy_ceiling": "65",
                "commodity_rsi_sell_floor": "70",
                "commodity_enabled_strategies": ["momentum", "macd"],
                "commodity_strategy_weights": '{"momentum": 2, "macd": 1}',
                "commodity_consensus_threshold": "0.50",
                "commodity_allocation_cap_fraction": "0.20",
                "stop_loss_fraction": "0.03",
                "take_profit_fraction": "0.06",
                "trailing_stop_fraction": "0.025",
                "maximum_drawdown_fraction": "0.15",
                "maximum_open_positions": "4",
                "risk_per_trade_fraction": "0.005",
                "maximum_total_risk_fraction": "0.02",
                "maximum_symbol_allocation_fraction": "0.25",
                "maximum_crypto_allocation_fraction": "0.60",
                "minimum_order_tmn": "50000",
                "symbol_loss_streak_limit": "3",
                "symbol_loss_limit_fraction": "0.05",
                "symbol_halt_days": "7",
                "market_data_stale_hours": "3",
                "paper_fee_fraction": "0.001",
                "paper_slippage_bps": "5",
                "paper_latency_ms": "500",
                "paper_max_book_participation": "0.10",
                "wallex_api_key": "read-only-secret",
            },
        )

        self.assertRedirects(response, reverse("trading:settings"))
        configuration = BotConfiguration.objects.get(name="default")
        self.assertNotIn(
            b"read-only-secret", bytes(configuration.wallex_api_key_encrypted)
        )
        self.assertEqual(configuration.get_wallex_api_key(), "read-only-secret")

    def test_market_chart_contains_price_and_paper_trade_points(self) -> None:
        strategy = Strategy.objects.create(name="BTC chart", symbol="BTCUSDT")
        MarketSnapshot.objects.create(symbol="BTCUSDT", last_price=Decimal("60000"))
        Trade.objects.create(
            strategy=strategy,
            side=Trade.Side.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("60000"),
            status=Trade.Status.FILLED,
            is_paper=True,
            executed_at=timezone.now(),
        )

        chart = build_market_chart_data(["BTCUSDT"])[0]

        self.assertEqual(len(chart["price_points"]), 1)
        self.assertEqual(len(chart["buy_points"]), 1)
        self.assertEqual(len(chart["sell_points"]), 0)

    def test_trade_csv_export_respects_symbol_filter(self) -> None:
        self.client.force_login(self.staff)
        btc = Strategy.objects.create(name="BTC export", symbol="BTCUSDT")
        eth = Strategy.objects.create(name="ETH export", symbol="ETHUSDT")
        for strategy in (btc, eth):
            Trade.objects.create(
                strategy=strategy,
                side=Trade.Side.BUY,
                quantity=Decimal("1"),
                requested_quantity=Decimal("1"),
                price=Decimal("100"),
                reference_price=Decimal("99"),
                status=Trade.Status.FILLED,
                is_paper=True,
                executed_at=timezone.now(),
            )

        response = self.client.get(
            reverse("trading:export_trades"), {"symbol": "BTCUSDT"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertContains(response, "BTCUSDT")
        self.assertNotContains(response, "ETHUSDT")

    def test_dashboard_displays_healthy_worker_heartbeat(self) -> None:
        self.client.force_login(self.staff)
        BotConfiguration.objects.create(
            name="default", enabled=True, symbols=["BTCUSDT"]
        )
        WorkerHeartbeat.objects.create(
            name="paper-trading-worker",
            status=WorkerHeartbeat.Status.HEALTHY,
            last_success_at=timezone.now(),
            cycles=7,
        )

        response = self.client.get(reverse("trading:dashboard"))

        self.assertContains(response, "Worker: Online")
        self.assertContains(response, "7 cycles")

    def test_staff_can_mark_alerts_as_read(self) -> None:
        from trading.models import Alert

        self.client.force_login(self.staff)
        alert = Alert.objects.create(
            alert_type=Alert.AlertType.WORKER,
            severity=Alert.Severity.WARNING,
            title="test",
            message="test alert",
            source_key="test:alert",
        )

        response = self.client.post(reverse("trading:mark_alerts_read"))

        self.assertRedirects(response, reverse("trading:dashboard"))
        alert.refresh_from_db()
        self.assertTrue(alert.is_read)
