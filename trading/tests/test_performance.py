from decimal import Decimal

from django.test import TestCase

from trading.services.performance import PerformanceAnalysisService, PerformanceMetrics


class PerformanceAnalysisServiceTests(TestCase):
    def test_calculates_profit_risk_and_trade_metrics(self) -> None:
        metrics: PerformanceMetrics = PerformanceAnalysisService().calculate(
            Decimal("100"),
            [Decimal("100"), Decimal("110"), Decimal("105"), Decimal("120")],
            [Decimal("10"), Decimal("-5"), Decimal("15")],
            periods_per_year=4,
        )

        self.assertEqual(metrics.net_profit, Decimal("20"))
        self.assertEqual(metrics.total_return, Decimal("0.2"))
        self.assertEqual(metrics.gross_profit, Decimal("25"))
        self.assertEqual(metrics.gross_loss, Decimal("5"))
        self.assertEqual(metrics.profit_factor, Decimal("5"))
        self.assertEqual(metrics.win_rate, Decimal("2") / Decimal("3"))
        self.assertEqual(metrics.maximum_drawdown, Decimal("5") / Decimal("110"))
        self.assertGreater(metrics.sharpe_ratio, Decimal("0"))
        self.assertGreater(metrics.sortino_ratio, Decimal("0"))

    def test_profit_factor_is_undefined_without_losses(self) -> None:
        metrics: PerformanceMetrics = PerformanceAnalysisService().calculate(
            Decimal("100"), [Decimal("100"), Decimal("105")], [Decimal("5")]
        )

        self.assertIsNone(metrics.profit_factor)
