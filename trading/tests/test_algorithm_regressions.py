from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from trading.models import (
    MarketSnapshot,
    TradingSignal,
    PaperWallet,
    Trade,
    OrderBookSnapshot,
)
from trading.services.base import Ticker
from trading.services.paper_trading import PaperTradingService
from trading.services.strategies.engine import (
    StrategyDecision,
    StrategyEngine,
    StrategySignal,
    SmaRsiStrategy,
)


class AlgorithmRegressionTests(TestCase):
    def test_wallet_profit_includes_both_buy_and_sell_fees(self) -> None:
        market = Mock()
        market.get_ticker.return_value = Ticker(
            symbol="BTCTMN",
            last_price=Decimal("100"),
            bid_price=Decimal("100"),
            ask_price=Decimal("100"),
            volume_24h=Decimal("100000"),
        )
        service = PaperTradingService(market_service=market)
        OrderBookSnapshot.objects.create(
            symbol="BTCTMN",
            best_bid=100,
            best_ask=100,
            bids=[["100", "100000"]],
            asks=[["100", "100000"]],
            bid_depth=100000,
            ask_depth=100000,
        )
        with patch.object(
            service,
            "_build_signal",
            side_effect=[
                (
                    "buy",
                    "test",
                    Decimal("1"),
                    [],
                    Decimal("105"),
                    Decimal("100"),
                    Decimal("35"),
                ),
                (
                    "sell",
                    "test",
                    Decimal("1"),
                    [],
                    Decimal("95"),
                    Decimal("100"),
                    Decimal("35"),
                ),
            ],
        ):
            service.run(("BTCTMN",))
            service.run(("BTCTMN",))
        wallet = PaperWallet.objects.get(asset="TMN")
        self.assertEqual(Trade.objects.count(), 2)
        self.assertAlmostEqual(
            wallet.realized_pnl,
            wallet.balance - wallet.initial_balance,
            places=6,
        )

    def test_equal_directional_scores_do_not_default_to_buy(self) -> None:
        with patch(
            "trading.services.strategies.engine.MomentumStrategy.evaluate",
            return_value=StrategyDecision("momentum", StrategySignal.BUY, 0.8, "test"),
        ), patch(
            "trading.services.strategies.engine.MacdStrategy.evaluate",
            return_value=StrategyDecision("macd", StrategySignal.SELL, 0.8, "test"),
        ):
            action, _, _, _ = StrategyEngine().evaluate(
                [100.0] * 40,
                ["momentum", "macd"],
                {},
                0.35,
            )
        self.assertEqual(action, StrategySignal.HOLD)

    def test_zero_rsi_is_preserved(self) -> None:
        analysis = Mock()
        analysis.sma.side_effect = [[101.0], [100.0]]
        analysis.rsi.return_value = [0.0]
        decision = SmaRsiStrategy(analysis, {"rsi_buy_ceiling": 30.0}).evaluate(
            [100.0] * 20
        )
        self.assertEqual(decision.signal, StrategySignal.BUY)
        self.assertIn("RSI=0.0", decision.reason)

    def test_ticks_are_not_used_as_hourly_candles(self) -> None:
        for price in range(100, 140):
            MarketSnapshot.objects.create(symbol="BTCTMN", last_price=Decimal(price))
        service = PaperTradingService(market_service=Mock())
        action, reason, confidence, *_ = service._build_signal("BTCTMN")
        self.assertEqual(action, TradingSignal.Action.HOLD)
        self.assertEqual(confidence, Decimal("0"))
        self.assertIn("closed hourly candles", reason)
