from django.test import SimpleTestCase

from trading.services.analysis import TechnicalAnalysisService


class TechnicalAnalysisServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.service: TechnicalAnalysisService = TechnicalAnalysisService()

    def test_simple_returns(self) -> None:
        result: tuple[float, ...] = self.service.simple_returns([100, 110, 99])

        self.assertAlmostEqual(result[0], 0.1)
        self.assertAlmostEqual(result[1], -0.1)

    def test_sma_preserves_input_length(self) -> None:
        result: tuple[float | None, ...] = self.service.sma([1, 2, 3, 4], 3)

        self.assertEqual(result, (None, None, 2.0, 3.0))

    def test_rsi_for_only_gains_is_one_hundred(self) -> None:
        result: tuple[float | None, ...] = self.service.rsi([1, 2, 3, 4], period=2)

        self.assertEqual(result[-1], 100.0)

    def test_bollinger_bands(self) -> None:
        result = self.service.bollinger_bands(
            [1, 2, 3], period=3, standard_deviations=2
        )

        self.assertEqual(result.middle[-1], 2.0)
        self.assertGreater(result.upper[-1], result.middle[-1])
        self.assertLess(result.lower[-1], result.middle[-1])

    def test_atr(self) -> None:
        result: tuple[float | None, ...] = self.service.atr(
            highs=[10, 12, 13], lows=[8, 9, 11], closes=[9, 11, 12], period=2
        )

        self.assertEqual(result, (None, 2.5, 2.25))

    def test_maximum_drawdown(self) -> None:
        result: float = self.service.maximum_drawdown([100, 120, 90, 110])

        self.assertEqual(result, -0.25)

    def test_fixed_fractional_position_size(self) -> None:
        result: float = self.service.fixed_fractional_position_size(
            10_000, 0.01, 100, 95
        )

        self.assertEqual(result, 20.0)
