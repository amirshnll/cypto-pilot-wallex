from decimal import Decimal

from django.test import TestCase

from trading.models import BotConfiguration, PaperPortfolio, PaperPosition, RiskEvent
from trading.services.risk import RiskManagementService


class RiskManagementServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration = BotConfiguration.objects.create(
            name="risk-test",
            symbols=["BTCUSDT"],
        )
        self.portfolio = PaperPortfolio.objects.create(
            name="risk-portfolio", initial_balance=100, cash_balance=100
        )
        self.position = PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("1"),
            average_entry_price=Decimal("100"),
        )
        self.service = RiskManagementService(self.configuration)
        self.service.initialize_position_limits(self.position, Decimal("100"))
        self.position.save()

    def test_stop_loss_forces_exit(self) -> None:
        decision = self.service.evaluate(
            self.portfolio, self.position, Decimal("96"), "hold"
        )

        self.assertTrue(decision.force_exit)
        self.assertEqual(decision.event_type, RiskEvent.EventType.STOP_LOSS)

    def test_emergency_stop_blocks_new_entry(self) -> None:
        self.position.quantity = Decimal("0")
        self.configuration.emergency_stop = True

        decision = self.service.evaluate(
            self.portfolio, self.position, Decimal("100"), "buy"
        )

        self.assertFalse(decision.allow_entry)
        self.assertEqual(decision.event_type, RiskEvent.EventType.EMERGENCY_STOP)
