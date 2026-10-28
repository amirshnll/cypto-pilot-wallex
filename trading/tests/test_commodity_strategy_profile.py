from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from trading.models import BotConfiguration, MarketCandle
from trading.services.commodity_optimization import CommodityWalkForwardOptimizer
from trading.services.strategy_profiles import is_commodity_symbol, profile_for


class OneCandidateOptimizer(CommodityWalkForwardOptimizer):
    def _candidates(self) -> list[dict[str, object]]:
        return [
            {
                "enabled_strategies": ["momentum"],
                "strategy_weights": {"momentum": 2.0},
                "consensus_threshold": 0.5,
                "fast_period": 3,
                "slow_period": 12,
                "rsi_period": 7,
                "rsi_buy_ceiling": 65.0,
                "rsi_sell_floor": 70.0,
            }
        ]


class CommodityStrategyProfileTests(TestCase):
    def setUp(self) -> None:
        self.configuration = BotConfiguration.objects.create(
            name="default",
            symbols=["BTCTMN", "XAUTTMN"],
            strategy_weights={"sma_rsi": 1},
            commodity_enabled_strategies=["momentum"],
            commodity_strategy_weights={"momentum": 2},
            commodity_consensus_threshold=Decimal("0.50"),
            commodity_fast_period=3,
            commodity_slow_period=12,
            commodity_rsi_period=7,
        )

    def test_crypto_and_commodity_profiles_are_independent(self) -> None:
        crypto = profile_for(self.configuration, "BTCTMN")
        commodity = profile_for(self.configuration, "XAUTTMN")
        self.assertEqual(crypto.asset_class, "crypto")
        self.assertEqual(commodity.asset_class, "commodity")
        self.assertEqual(crypto.fast_period, 5)
        self.assertEqual(commodity.fast_period, 3)
        self.assertEqual(commodity.strategy_weights, {"momentum": 2.0})
        self.assertTrue(is_commodity_symbol("USOONTMN"))
        self.assertFalse(is_commodity_symbol("USDTTMN"))

    def test_walk_forward_report_can_be_applied_to_commodity_profile(self) -> None:
        start = timezone.now() - timedelta(hours=260)
        MarketCandle.objects.bulk_create(
            [
                MarketCandle(
                    symbol="XAUTTMN",
                    resolution="60",
                    opened_at=start + timedelta(hours=index),
                    open_price=Decimal(100 + index),
                    high_price=Decimal(102 + index),
                    low_price=Decimal(99 + index),
                    close_price=Decimal("100.5") + index,
                    volume=Decimal("10"),
                )
                for index in range(250)
            ]
        )
        result = OneCandidateOptimizer(self.configuration).optimize(
            ("XAUTTMN",), apply=True
        )
        self.configuration.refresh_from_db()
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.eligible_symbols, ("XAUTTMN",))
        self.assertEqual(self.configuration.commodity_fast_period, 3)
        self.assertEqual(
            self.configuration.commodity_strategy_weights, {"momentum": 2.0}
        )
        self.assertEqual(
            self.configuration.commodity_optimization_report["method"],
            "expanding-history walk-forward",
        )
