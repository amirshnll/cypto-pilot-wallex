from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from trading.models import (
    BotConfiguration,
    MarketCandle,
    MarketRegimeSnapshot,
    StrategyOptimizationRun,
)
from trading.services.optimization import (
    MarketRegimeDetector,
    OptimizationResult,
    StrategyOptimizationService,
)


class StrategyOptimizationServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration = BotConfiguration.objects.create(
            name="default",
            symbols=["BTCUSDT"],
            enabled_strategies=["momentum"],
            consensus_threshold=Decimal("0.35"),
        )
        start = timezone.now() - timedelta(hours=150)
        MarketCandle.objects.bulk_create(
            [
                MarketCandle(
                    symbol="BTCUSDT",
                    resolution="60",
                    opened_at=start + timedelta(hours=index),
                    open_price=Decimal(100 + index),
                    high_price=Decimal(102 + index),
                    low_price=Decimal(99 + index),
                    close_price=Decimal("100.5") + index,
                    volume=Decimal("10"),
                )
                for index in range(150)
            ]
        )

    def test_optimization_uses_unseen_test_and_records_sensitivity(self) -> None:
        result: OptimizationResult = StrategyOptimizationService(
            self.configuration
        ).optimize("BTCUSDT")

        run = StrategyOptimizationRun.objects.get(pk=result.run_id)
        self.assertEqual(run.status, StrategyOptimizationRun.Status.COMPLETED)
        self.assertGreater(run.candidate_count, 0)
        self.assertEqual(len(run.sensitivity), 5)
        self.assertTrue(run.top_candidates)
        self.assertIn("consensus_threshold", result.best_parameters)
        self.assertEqual(
            MarketRegimeSnapshot.objects.filter(symbol="BTCUSDT").count(), 1
        )

    def test_regime_detector_identifies_uptrend(self) -> None:
        regime = MarketRegimeDetector().detect(
            "ETHUSDT", [float(100 + index) for index in range(60)]
        )

        self.assertEqual(regime.regime, MarketRegimeSnapshot.Regime.TREND_UP)

    def test_optimization_rejects_short_history(self) -> None:
        ids = list(
            MarketCandle.objects.filter(symbol="BTCUSDT")
            .order_by("opened_at")
            .values_list("pk", flat=True)[:40]
        )
        MarketCandle.objects.filter(pk__in=ids).delete()

        with self.assertRaisesRegex(ValueError, "needs at least 120 candles"):
            StrategyOptimizationService(self.configuration).optimize("BTCUSDT")
