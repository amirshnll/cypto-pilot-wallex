from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from trading.models import (
    BotConfiguration,
    MarketCandle,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    RiskEvent,
    Strategy,
    Trade,
)
from trading.services.paper_trading import PaperTradingService
from trading.services.risk import RiskDecision, RiskManagementService


@override_settings(PAPER_REENTRY_COOLDOWN_MINUTES=60)
class EntrySafetyTests(TestCase):
    def setUp(self) -> None:
        self.portfolio = PaperPortfolio.objects.create(
            name="safety", initial_balance=100, cash_balance=100
        )
        self.strategy = Strategy.objects.create(name="safety", symbol="BTCTMN")
        self.service = PaperTradingService(market_service=Mock())
        self.now = timezone.now().replace(minute=30, second=0, microsecond=0)

    def exit(self, minutes: int, status: str = Trade.Status.FILLED) -> Trade:
        return Trade.objects.create(
            portfolio=self.portfolio,
            strategy=self.strategy,
            side=Trade.Side.SELL,
            quantity=1,
            price=100,
            notional=100,
            status=status,
            executed_at=self.now - timedelta(minutes=minutes),
        )

    def candle(self, hours: int) -> None:
        MarketCandle.objects.create(
            symbol="BTCTMN",
            resolution="60",
            opened_at=self.now.replace(minute=0) - timedelta(hours=hours),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1,
        )

    def test_first_entry_is_not_blocked(self) -> None:
        self.assertIsNone(self.service._reentry_block_reason(self.portfolio, "BTCTMN"))

    def test_recent_exit_blocks_reentry(self) -> None:
        self.exit(5)
        with patch(
            "trading.services.paper_trading.timezone.now", return_value=self.now
        ):
            self.assertEqual(
                self.service._reentry_block_reason(self.portfolio, "BTCTMN"),
                "re-entry cooldown is active",
            )

    def test_stale_candle_blocks_reentry_after_cooldown(self) -> None:
        self.exit(90)
        self.candle(3)
        with patch(
            "trading.services.paper_trading.timezone.now", return_value=self.now
        ):
            self.assertEqual(
                self.service._reentry_block_reason(self.portfolio, "BTCTMN"),
                "waiting for a new closed candle after exit",
            )

    def test_new_closed_candle_allows_reentry(self) -> None:
        self.exit(90)
        self.candle(1)
        with patch(
            "trading.services.paper_trading.timezone.now", return_value=self.now
        ):
            self.assertIsNone(
                self.service._reentry_block_reason(self.portfolio, "BTCTMN")
            )

    def test_rejected_exit_does_not_block_entry(self) -> None:
        self.exit(5, Trade.Status.REJECTED)
        self.assertIsNone(self.service._reentry_block_reason(self.portfolio, "BTCTMN"))

    @override_settings(PAPER_REENTRY_COOLDOWN_MINUTES=0)
    def test_cooldown_can_be_disabled(self) -> None:
        self.exit(5)
        self.assertIsNone(self.service._reentry_block_reason(self.portfolio, "BTCTMN"))

    def test_drawdown_uses_records_after_first_thousand(self) -> None:
        PaperPortfolioSnapshot.objects.bulk_create(
            [
                PaperPortfolioSnapshot(
                    portfolio=self.portfolio,
                    cash_balance=100,
                    positions_value=0,
                    total_equity=100,
                    realized_pnl=0,
                    wallet_balances={"TMN": "100"},
                )
                for _ in range(1000)
            ]
        )
        PaperPortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            cash_balance=80,
            positions_value=0,
            total_equity=80,
            realized_pnl=0,
            wallet_balances={"TMN": "80"},
        )
        self.assertEqual(
            RiskManagementService.portfolio_drawdown(self.portfolio, "TMN"),
            Decimal("-0.2"),
        )

    def test_position_limit_events_are_throttled_but_checks_remain(self) -> None:
        config = BotConfiguration.objects.create(
            name="safety", maximum_open_positions=1
        )
        position = PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="BTCTMN",
            quantity=1,
            average_entry_price=100,
            highest_price=100,
            quote_asset="TMN",
        )
        manager = RiskManagementService(config)
        self.assertFalse(
            manager.evaluate(
                self.portfolio, position, Decimal("100"), "buy"
            ).allow_entry
        )
        self.assertFalse(
            manager.evaluate(
                self.portfolio, position, Decimal("100"), "buy"
            ).allow_entry
        )
        self.assertEqual(
            RiskEvent.objects.filter(event_type="position_limit").count(), 1
        )
        RiskEvent.objects.update(created_at=timezone.now() - timedelta(hours=2))
        manager.evaluate(self.portfolio, position, Decimal("100"), "buy")
        self.assertEqual(
            RiskEvent.objects.filter(event_type="position_limit").count(), 2
        )
