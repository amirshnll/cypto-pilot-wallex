from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from trading.services.strategies import StrategySignal

from trading.models import BacktestFold, BacktestRun, BotConfiguration, MarketCandle
from trading.services.backtesting import BacktestResult, BacktestingService


class BacktestingServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration: BotConfiguration = BotConfiguration.objects.create(
            name="default",
            symbols=["BTCUSDT"],
            initial_balance=Decimal("100"),
            enabled_strategies=["momentum"],
            consensus_threshold=Decimal("0.10"),
            paper_fee_fraction=Decimal("0.001"),
            paper_slippage_bps=Decimal("5"),
        )
        start = timezone.now() - timedelta(hours=200)
        MarketCandle.objects.bulk_create(
            [
                MarketCandle(
                    symbol="BTCUSDT",
                    resolution="60",
                    opened_at=start + timedelta(hours=index),
                    open_price=Decimal(100 + index),
                    high_price=Decimal(101 + index),
                    low_price=Decimal(99 + index),
                    close_price=Decimal("100.5") + Decimal(index),
                    volume=Decimal("10"),
                )
                for index in range(200)
            ]
        )

    def test_walk_forward_persists_folds_and_benchmark(self) -> None:
        result: BacktestResult = BacktestingService(self.configuration).run(
            "BTCUSDT", train_size=100, test_size=50
        )

        run: BacktestRun = BacktestRun.objects.get(pk=result.run_id)
        self.assertEqual(run.status, BacktestRun.Status.COMPLETED)
        self.assertEqual(result.fold_count, 2)
        self.assertEqual(BacktestFold.objects.filter(run=run).count(), 2)
        self.assertEqual(
            result.excess_return, result.total_return - result.buy_hold_return
        )
        self.assertEqual(run.parameters["execution"], "next_candle_open")
        self.assertEqual(len(run.equity_curve), 100)

    def test_rejects_insufficient_history(self) -> None:
        with self.assertRaisesRegex(ValueError, "needs at least 250 candles"):
            BacktestingService(self.configuration).run(
                "BTCUSDT", train_size=200, test_size=50
            )

    def test_take_profit_exits_without_a_sell_signal(self) -> None:
        self.configuration.take_profit_fraction = Decimal("0.01")
        service = BacktestingService(self.configuration)
        with patch.object(
            service.engine,
            "evaluate",
            return_value=(StrategySignal.BUY, 1.0, "buy", ()),
        ):
            result = service.run("BTCUSDT", train_size=100, test_size=50)
        self.assertGreater(result.trade_count, 1)
        self.assertEqual(
            BacktestRun.objects.get(pk=result.run_id).parameters["risk_policy"],
            "shared-v2",
        )
