from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from trading.models import (
    MarketSnapshot,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperWallet,
    TradingSignal,
)
from trading.services.base import MarketAPIError, Ticker
from trading.services.paper_trading import PaperBotResult, PaperTradingService
from trading.services.trade_policy import TradePolicy
from trading.models import BotConfiguration


class PaperTradingServiceTests(TestCase):
    def test_run_persists_market_signal_and_portfolio_history(self) -> None:
        market_service: Mock = Mock()
        market_service.get_ticker.return_value = Ticker(
            symbol="BTCTMN",
            last_price=Decimal("12000000000"),
            bid_price=Decimal("11999000000"),
            ask_price=Decimal("12001000000"),
            volume_24h=Decimal("100"),
        )
        service: PaperTradingService = PaperTradingService(
            market_service=market_service
        )

        results: tuple[PaperBotResult, ...] = service.run(("BTCTMN",))

        self.assertEqual(results[0].action, TradingSignal.Action.HOLD)
        self.assertEqual(MarketSnapshot.objects.count(), 1)
        self.assertEqual(TradingSignal.objects.count(), 1)
        self.assertEqual(PaperPortfolio.objects.count(), 1)
        self.assertEqual(
            PaperWallet.objects.get(asset="TMN").balance, Decimal("1000000")
        )
        self.assertEqual(PaperPortfolioSnapshot.objects.count(), 1)
        self.assertEqual(
            PaperPortfolioSnapshot.objects.get().total_equity, Decimal("1000000")
        )

    def test_bot_calculates_position_size_from_signal_confidence(self) -> None:
        signal: Mock = Mock(
            fast_sma=Decimal("105"),
            slow_sma=Decimal("100"),
            rsi=Decimal("35"),
        )

        fraction: Decimal = TradePolicy(BotConfiguration()).budget(
            "BTCTMN", Decimal("1000000"), Decimal("1000000"), Decimal("0.5"), []
        ).cash / Decimal("1000000")

        self.assertGreater(fraction, Decimal("0"))
        self.assertLessEqual(fraction, Decimal("1"))

    def test_high_risk_allocates_more_than_low_risk(self) -> None:
        signal: Mock = Mock(
            fast_sma=Decimal("105"),
            slow_sma=Decimal("100"),
            rsi=Decimal("35"),
        )

        low: Decimal = (
            TradePolicy(BotConfiguration(risk_level="low", minimum_order_tmn=0))
            .budget(
                "BTCTMN", Decimal("1000000"), Decimal("1000000"), Decimal("0.5"), []
            )
            .cash
        )
        high: Decimal = (
            TradePolicy(BotConfiguration(risk_level="high", minimum_order_tmn=0))
            .budget(
                "BTCTMN", Decimal("1000000"), Decimal("1000000"), Decimal("0.5"), []
            )
            .cash
        )

        self.assertGreater(high, low)

    def test_symbol_split_keeps_quote_wallets_separate(self) -> None:
        self.assertEqual(PaperTradingService._split_symbol("BTCUSDT"), ("BTC", "USDT"))
        self.assertEqual(PaperTradingService._split_symbol("BTCTMN"), ("BTC", "TMN"))
        self.assertEqual(PaperTradingService._split_symbol("USDTTMN"), ("USDT", "TMN"))

    def test_one_unavailable_market_does_not_stop_other_symbols(self) -> None:
        market_service: Mock = Mock()
        market_service.get_ticker.side_effect = [
            MarketAPIError("temporarily unavailable"),
            Ticker(
                symbol="ETHTMN",
                last_price=Decimal("100"),
                bid_price=Decimal("99"),
                ask_price=Decimal("101"),
                volume_24h=Decimal("10"),
            ),
        ]
        service = PaperTradingService(market_service=market_service)

        results = service.run(("PPLTONTMN", "ETHTMN"))

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].symbol, "PPLTONTMN")
        self.assertEqual(results[0].action, TradingSignal.Action.HOLD)
        self.assertIn("market data unavailable", results[0].reason)
        self.assertEqual(results[1].symbol, "ETHTMN")
        self.assertEqual(MarketSnapshot.objects.filter(symbol="ETHTMN").count(), 1)
