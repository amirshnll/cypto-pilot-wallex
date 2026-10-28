from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from trading.models import BotConfiguration, PaperPortfolio, RiskEvent, SymbolRiskState
from trading.services.symbol_risk import SymbolRiskService


class SymbolRiskServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration = BotConfiguration.objects.create(
            name="symbol-risk",
            symbols=["BTCTMN"],
            strategy_weights={"sma_rsi": 1},
            symbol_loss_streak_limit=3,
            symbol_loss_limit_fraction=Decimal("0.05"),
            symbol_halt_days=7,
        )
        self.portfolio = PaperPortfolio.objects.create(
            name="symbol-risk",
            initial_balance=Decimal("1000"),
            cash_balance=Decimal("1000"),
        )
        self.service = SymbolRiskService(self.configuration)

    def test_three_consecutive_losses_halt_only_that_symbol_for_seven_days(
        self,
    ) -> None:
        now = timezone.now()
        with patch("trading.services.symbol_risk.timezone.now", return_value=now):
            self.service.record_execution(self.portfolio, "BTCTMN", Decimal("-1"))
            self.service.record_execution(self.portfolio, "BTCTMN", Decimal("-2"))
            state = self.service.record_execution(
                self.portfolio, "BTCTMN", Decimal("-3")
            )
            result = self.service.entry_status(self.portfolio, "BTCTMN")
            other = self.service.entry_status(self.portfolio, "ETHTMN")
        self.assertEqual(state.consecutive_losses, 3)
        self.assertEqual(state.halted_until, now + timedelta(days=7))
        self.assertTrue(result.halted)
        self.assertFalse(other.halted)
        self.assertEqual(
            RiskEvent.objects.filter(
                event_type=RiskEvent.EventType.SYMBOL_HALT, symbol="BTCTMN"
            ).count(),
            1,
        )

    def test_symbol_loss_cap_halts_before_streak_limit(self) -> None:
        state = self.service.record_execution(self.portfolio, "BTCTMN", Decimal("-51"))
        self.assertIsNotNone(state.halted_until)
        self.assertIn("loss cap", state.halt_reason)

    def test_profitable_execution_resets_consecutive_loss_count(self) -> None:
        self.service.record_execution(self.portfolio, "BTCTMN", Decimal("-1"))
        state = self.service.record_execution(self.portfolio, "BTCTMN", Decimal("2"))
        self.assertEqual(state.consecutive_losses, 0)
        self.assertEqual(state.cycle_realized_pnl, Decimal("1"))

    def test_expired_halt_resets_cycle_and_allows_entry(self) -> None:
        state = SymbolRiskState.objects.create(
            portfolio=self.portfolio,
            symbol="BTCTMN",
            consecutive_losses=3,
            cycle_realized_pnl=Decimal("-10"),
            halted_until=timezone.now() - timedelta(seconds=1),
            halt_reason="test",
        )
        result = self.service.entry_status(self.portfolio, "BTCTMN")
        self.assertFalse(result.halted)
        state.refresh_from_db()
        self.assertEqual(state.consecutive_losses, 0)
        self.assertEqual(state.cycle_realized_pnl, Decimal("0"))
        self.assertIsNone(state.halted_until)

    def test_admin_values_control_halt_duration_and_streak(self) -> None:
        self.configuration.symbol_loss_streak_limit = 2
        self.configuration.symbol_halt_days = 4
        self.configuration.save()
        now = timezone.now()
        service = SymbolRiskService(self.configuration)
        with patch("trading.services.symbol_risk.timezone.now", return_value=now):
            service.record_execution(self.portfolio, "BTCTMN", Decimal("-1"))
            state = service.record_execution(self.portfolio, "BTCTMN", Decimal("-1"))
        self.assertEqual(state.halted_until, now + timedelta(days=4))
