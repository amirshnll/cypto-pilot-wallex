from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from unittest.mock import patch
from django.test import SimpleTestCase
from django.test import TestCase
from unittest.mock import Mock
from trading.models import BotConfiguration, MarketCandle
from trading.services.entry_research import entry_allowed, VARIANTS
from trading.services.portfolio_research import replay
from trading.services.strategies import StrategySignal
from trading.services.paper_trading import PaperTradingService
from trading.services.candles import last_closed_open_time


class EntryResearchTests(SimpleTestCase):
    def candles(self, count: int = 101, rising: bool = True) -> list[MarketCandle]:
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        rows = []
        for i in range(count):
            p = D(100 + i if rising else 200 - i)
            rows.append(
                MarketCandle(
                    symbol="BTCTMN",
                    resolution="60",
                    opened_at=start + timedelta(hours=i),
                    open_price=p,
                    high_price=p + 2,
                    low_price=p - 2,
                    close_price=p,
                    volume=100,
                )
            )
        return rows

    def test_trend_accepts_rising_and_rejects_falling(self) -> None:
        config = BotConfiguration()
        for rising, expected in ((True, True), (False, False)):
            rows = self.candles(rising=rising)
            allowed, _ = entry_allowed(
                rows[:100], rows[100].opened_at, config, VARIANTS[1]
            )
            self.assertEqual(allowed, expected)

    def test_future_candle_is_ignored(self) -> None:
        rows = self.candles()
        at = rows[100].opened_at
        first = entry_allowed(rows[:100], at, BotConfiguration(), VARIANTS[1])
        rows[100].close_price = D("0.01")
        self.assertEqual(
            first, entry_allowed(rows, at, BotConfiguration(), VARIANTS[1])
        )

    def test_gap_blocks_filter(self) -> None:
        rows = self.candles(102)
        del rows[70]
        allowed, reason = entry_allowed(
            rows[:-1], rows[-1].opened_at, BotConfiguration(), VARIANTS[1]
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "gapped_history")

    def test_flat_range_is_not_assumed_profitable_after_cost(self) -> None:
        rows = self.candles()
        for row in rows:
            row.high_price = D("100.1")
            row.low_price = D("99.9")
            row.close_price = row.open_price = D("100")
        self.assertFalse(
            entry_allowed(
                rows[:100], rows[100].opened_at, BotConfiguration(), VARIANTS[2]
            )[0]
        )

    def test_intrabar_sale_cannot_fund_another_open_entry(self) -> None:
        a, b = self.candles(), self.candles()
        a[-1].high_price = D("500")
        config = BotConfiguration(
            symbols=["BTCTMN", "ETHTMN"],
            initial_tmn_balance=D("1000000"),
            maximum_open_positions=1,
        )
        with patch(
            "trading.services.portfolio_research.StrategyEngine.evaluate",
            return_value=(StrategySignal.BUY, 1, "test", ()),
        ):
            result = replay(
                config,
                {"BTCTMN": a, "ETHTMN": b},
                a[-1].opened_at,
                a[-1].opened_at,
                VARIANTS[0],
            )
        self.assertEqual(result["buys"], 1)
        self.assertEqual(result["closed_positions"], 1)


class ResearchObservationTests(TestCase):
    def test_shadow_rejection_cannot_change_actual_strategy_signal(self) -> None:
        end = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ) - timedelta(hours=1)
        MarketCandle.objects.bulk_create(
            [
                MarketCandle(
                    symbol="BTCTMN",
                    resolution="60",
                    opened_at=end - timedelta(hours=99 - i),
                    open_price=200 - i,
                    high_price=202 - i,
                    low_price=198 - i,
                    close_price=200 - i,
                    volume=100,
                )
                for i in range(100)
            ]
        )
        service = PaperTradingService(market_service=Mock())
        with patch.object(
            service.strategy_engine,
            "evaluate",
            return_value=(StrategySignal.BUY, 0.8, "raw buy", ()),
        ):
            action, reason, confidence, components, *_ = service._build_signal("BTCTMN")
        self.assertEqual(action, "buy")
        self.assertEqual(reason, "raw buy")
        self.assertEqual(confidence, D("0.8"))
        trend = next(c for c in components if c["strategy"] == "research:trend_4h")
        self.assertEqual(trend["signal"], "block")
        self.assertEqual(trend["mode"], "shadow_only")
        self.assertEqual(
            trend["candle_boundary"], (end + timedelta(hours=1)).isoformat()
        )

    def test_rising_closed_history_passes_shadow_trend(self) -> None:
        end = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ) - timedelta(hours=1)
        MarketCandle.objects.bulk_create(
            [
                MarketCandle(
                    symbol="BTCTMN",
                    resolution="60",
                    opened_at=end - timedelta(hours=99 - i),
                    open_price=200 + i,
                    high_price=202 + i,
                    low_price=198 + i,
                    close_price=200 + i,
                    volume=100,
                )
                for i in range(100)
            ]
        )
        service = PaperTradingService(market_service=Mock())
        with patch.object(
            service.strategy_engine,
            "evaluate",
            return_value=(StrategySignal.BUY, 0.8, "raw buy", ()),
        ):
            _, _, _, components, *_ = service._build_signal("BTCTMN")
        trend = next(c for c in components if c["strategy"] == "research:trend_4h")
        self.assertEqual(trend["signal"], "pass")
