from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from trading.models import (
    BotConfiguration,
    PaperPortfolio,
    PaperWallet,
    PaperPosition,
    MarketSnapshot,
    OrderBookSnapshot,
    Trade,
)
from trading.services.trade_policy import TradePolicy, Exposure
from trading.services.risk import RiskManagementService
from trading.services.paper_execution import PaperExecutionService


class TradePolicyTests(TestCase):
    def setUp(self) -> None:
        self.config = BotConfiguration.objects.create(
            name="policy", risk_level="medium"
        )
        self.policy = TradePolicy(self.config)

    def test_larger_stop_means_smaller_order(self) -> None:
        first = self.policy.budget(
            "BTCTMN", D("1000000"), D("1000000"), D("1"), []
        ).cash
        self.config.stop_loss_fraction = D("0.10")
        self.config.minimum_order_tmn = 0
        second = self.policy.budget(
            "BTCTMN", D("1000000"), D("1000000"), D("1"), []
        ).cash
        self.assertLess(second, first)

    def test_crypto_group_cap_rejects_extra_entry(self) -> None:
        result = self.policy.budget(
            "ETHTMN",
            D("400000"),
            D("1000000"),
            D("1"),
            [Exposure("BTCTMN", D("600000"), D("5000"))],
        )
        self.assertEqual(result.cash, 0)

    def test_small_remaining_commodity_capacity_is_not_traded(self) -> None:
        result = self.policy.budget(
            "SLVONTMN",
            D("801000"),
            D("1000000"),
            D("1"),
            [Exposure("UNGONTMN", D("199000"), D("5000"))],
        )
        self.assertEqual(result.cash, 0)

    def test_total_open_risk_caps_new_orders(self) -> None:
        result = self.policy.budget(
            "BTCTMN",
            D("500000"),
            D("1000000"),
            D("1"),
            [Exposure("XAUTTMN", D("200000"), D("20000"))],
        )
        self.assertEqual(result.cash, 0)

    def test_zero_signal_has_no_budget(self) -> None:
        self.assertEqual(
            self.policy.budget("BTCTMN", D("1000000"), D("1000000"), D("0"), []).cash, 0
        )

    def test_round_trip_cost_and_stop_fit_the_configured_risk(self) -> None:
        result = self.policy.budget("BTCTMN", D("1000000"), D("1000000"), D("1"), [])
        notional = result.cash / (D("1") + self.config.paper_fee_fraction)
        loss = notional * (
            self.config.stop_loss_fraction
            + self.config.paper_fee_fraction * 2
            + self.config.paper_slippage_bps / D("10000") * 2
        )
        self.assertLessEqual(loss, D("5000.000001"))

    def test_worse_gap_price_is_used_before_candle_stop_threshold(self) -> None:
        self.assertEqual(
            self.policy.exit_reason(D("80"), D("97"), D("106"), D("98")),
            "stop-loss triggered",
        )

    def test_drawdown_detected_on_hold_with_live_valuation(self) -> None:
        portfolio = PaperPortfolio.objects.create(
            name="test", initial_balance=1000000, cash_balance=0
        )
        PaperWallet.objects.create(
            portfolio=portfolio, asset="TMN", initial_balance=1000000, balance=0
        )
        position = PaperPosition.objects.create(
            portfolio=portfolio,
            symbol="BTCTMN",
            quote_asset="TMN",
            quantity=1,
            average_entry_price=1000000,
        )
        MarketSnapshot.objects.create(symbol="BTCTMN", last_price=800000)
        RiskManagementService(self.config).evaluate(
            portfolio, position, D("800000"), "hold"
        )
        self.config.refresh_from_db()
        self.assertTrue(self.config.risk_halted)

    def test_stale_book_does_not_fill(self) -> None:
        book = OrderBookSnapshot.objects.create(
            symbol="BTCTMN",
            best_bid=100,
            best_ask=101,
            bids=[["100", "100"]],
            asks=[["101", "100"]],
            bid_depth=100,
            ask_depth=100,
        )
        OrderBookSnapshot.objects.filter(pk=book.pk).update(
            captured_at=timezone.now() - timedelta(hours=1)
        )
        self.assertIsNone(
            PaperExecutionService(self.config).execute(
                "BTCTMN", Trade.Side.BUY, D("1"), D("100"), D("101")
            )
        )
