from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from trading.models import MarketCandle, MarketHealthState, TradingSignal
from trading.services.base import Ticker
from trading.services.market_freshness import MarketFreshnessService
from trading.services.paper_trading import PaperTradingService


class MarketFreshnessServiceTests(TestCase):
    def candle(self, symbol: str, opened_at) -> MarketCandle:
        return MarketCandle.objects.create(
            symbol=symbol,
            resolution="60",
            opened_at=opened_at,
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1,
        )

    def test_stale_market_is_disabled_but_fresh_data_reenables_it(self) -> None:
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        candle = self.candle("PPLTONTMN", now - timedelta(hours=8))
        service = MarketFreshnessService(stale_after_hours=3)

        stale = service.refresh("PPLTONTMN", checked_at=now)
        self.assertFalse(stale.trading_enabled)
        candle.delete()
        self.candle("PPLTONTMN", now - timedelta(hours=1))
        fresh = service.refresh("PPLTONTMN", checked_at=now)

        self.assertTrue(fresh.trading_enabled)
        state = MarketHealthState.objects.get(symbol="PPLTONTMN")
        self.assertTrue(state.trading_enabled)
        self.assertIsNone(state.disabled_at)

    def test_missing_market_data_is_disabled(self) -> None:
        result = MarketFreshnessService(3).refresh("PPLTONTMN")
        self.assertFalse(result.trading_enabled)
        self.assertIn("no closed", result.reason)

    def test_stale_market_forces_hold_in_paper_bot(self) -> None:
        market = Mock()
        market.get_ticker.return_value = Ticker(
            symbol="BTCTMN",
            last_price=Decimal("100"),
            bid_price=Decimal("99"),
            ask_price=Decimal("101"),
            volume_24h=Decimal("1"),
        )
        MarketHealthState.objects.create(
            symbol="BTCTMN",
            trading_enabled=False,
            reason="market data is stale",
        )
        service = PaperTradingService(market_service=market)

        result = service.run(("BTCTMN",))[0]

        self.assertEqual(result.action, TradingSignal.Action.HOLD)
        self.assertEqual(result.reason, "market data is stale")
