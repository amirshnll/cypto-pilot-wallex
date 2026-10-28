from decimal import Decimal

from django.test import TestCase

from trading.models import BotConfiguration, OrderBookSnapshot, Trade
from trading.services.paper_execution import PaperExecution, PaperExecutionService


class PaperExecutionServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration: BotConfiguration = BotConfiguration(
            paper_fee_fraction=Decimal("0.001"),
            paper_slippage_bps=Decimal("4"),
            paper_latency_ms=500,
            paper_max_book_participation=Decimal("0.50"),
        )
        OrderBookSnapshot.objects.create(
            symbol="BTCUSDT",
            best_bid=Decimal("99"),
            best_ask=Decimal("101"),
            bids=[["99", "2"], ["98", "4"]],
            asks=[["101", "1"], ["102", "3"]],
            bid_depth=Decimal("6"),
            ask_depth=Decimal("4"),
        )

    def test_buy_uses_ask_walks_book_and_charges_fee(self) -> None:
        execution: PaperExecution | None = PaperExecutionService(
            self.configuration
        ).execute(
            "BTCUSDT", Trade.Side.BUY, Decimal("2"), Decimal("99"), Decimal("101")
        )

        self.assertIsNotNone(execution)
        assert execution is not None
        self.assertEqual(execution.reference_price, Decimal("101"))
        self.assertGreater(execution.execution_price, Decimal("101.5"))
        self.assertGreater(execution.fee_amount, Decimal("0"))
        self.assertLess(execution.net_cash_change, Decimal("0"))

    def test_liquidity_caps_fill_and_marks_fraction(self) -> None:
        execution: PaperExecution | None = PaperExecutionService(
            self.configuration
        ).execute(
            "BTCUSDT", Trade.Side.SELL, Decimal("10"), Decimal("99"), Decimal("101")
        )

        self.assertIsNotNone(execution)
        assert execution is not None
        self.assertEqual(execution.filled_quantity, Decimal("3.0"))
        self.assertEqual(execution.liquidity_fraction, Decimal("0.3"))
        self.assertLess(execution.execution_price, Decimal("99"))

    def test_missing_order_book_does_not_invent_liquidity(self) -> None:
        execution: PaperExecution | None = PaperExecutionService(
            self.configuration
        ).execute(
            "ETHUSDT", Trade.Side.BUY, Decimal("1"), Decimal("1999"), Decimal("2001")
        )

        self.assertIsNone(execution)
