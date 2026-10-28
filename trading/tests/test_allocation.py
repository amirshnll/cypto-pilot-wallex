from decimal import Decimal

from django.test import TestCase

from trading.models import (
    BotConfiguration,
    MarketSnapshot,
    PaperPortfolio,
    PaperPosition,
    PaperWallet,
)
from trading.services.allocation import CommodityAllocationService


class CommodityAllocationServiceTests(TestCase):
    def setUp(self) -> None:
        self.configuration = BotConfiguration(
            name="allocation-test",
            commodity_allocation_cap_fraction=Decimal("0.20"),
        )
        self.portfolio = PaperPortfolio.objects.create(
            name="Allocation test",
            quote_asset="TMN",
            initial_balance=Decimal("1000000"),
            cash_balance=Decimal("700000"),
        )
        self.wallet = PaperWallet.objects.create(
            portfolio=self.portfolio,
            asset="TMN",
            initial_balance=Decimal("1000000"),
            balance=Decimal("700000"),
        )
        self.service = CommodityAllocationService(self.configuration)

    def add_position(self, symbol: str, value: Decimal) -> None:
        PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol=symbol,
            base_asset=symbol[:-3],
            quote_asset="TMN",
            quantity=Decimal("1"),
            average_entry_price=value,
        )
        MarketSnapshot.objects.create(symbol=symbol, last_price=value)

    def test_combines_all_commodity_exposure_against_portfolio_equity(self) -> None:
        self.add_position("USOONTMN", Decimal("120000"))
        self.add_position("XAUTTMN", Decimal("80000"))
        self.add_position("BTCTMN", Decimal("100000"))

        decision = self.service.evaluate(self.portfolio, self.wallet, "SLVONTMN")

        self.assertEqual(decision.current_exposure, Decimal("200000"))
        self.assertEqual(decision.cap_amount, Decimal("200000.00"))
        self.assertEqual(decision.available_amount, Decimal("0"))
        self.assertFalse(decision.allowed)

    def test_remaining_capacity_is_returned_for_order_clamping(self) -> None:
        self.add_position("USOONTMN", Decimal("100000"))

        decision = self.service.evaluate(self.portfolio, self.wallet, "XAUTTMN")

        self.assertEqual(decision.cap_amount, Decimal("160000.00"))
        self.assertEqual(decision.available_amount, Decimal("60000.00"))
        self.assertTrue(decision.allowed)

    def test_crypto_entry_is_not_restricted_by_commodity_cap(self) -> None:
        self.add_position("USOONTMN", Decimal("300000"))

        decision = self.service.evaluate(self.portfolio, self.wallet, "BTCTMN")

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.available_amount, self.wallet.balance)
