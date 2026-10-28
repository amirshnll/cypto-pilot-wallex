from django.test import SimpleTestCase

from trading.services.strategies import StrategyEngine, StrategySignal


class StrategyEngineTests(SimpleTestCase):
    def setUp(self) -> None:
        self.engine = StrategyEngine()

    def test_engine_returns_component_decisions(self) -> None:
        closes = [100 + index * 0.5 for index in range(60)]

        signal, confidence, reason, decisions = self.engine.evaluate(
            closes,
            ["sma_rsi", "momentum", "macd", "bollinger", "breakout"],
            {},
            0.2,
        )

        self.assertIn(signal, StrategySignal)
        self.assertGreaterEqual(confidence, 0)
        self.assertEqual(len(decisions), 5)
        self.assertIn("macd=", reason)

    def test_engine_holds_during_warmup(self) -> None:
        signal, confidence, _reason, decisions = self.engine.evaluate(
            [100, 101], ["macd"], {}, 0.35
        )

        self.assertEqual(signal, StrategySignal.HOLD)
        self.assertEqual(confidence, 0.1)
        self.assertIn("warm-up", decisions[0].reason)
