from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from trading.models import MLFeatureRow, MLTrainingRun, MarketCandle
from trading.services.machine_learning import (
    FeatureEngineeringService,
    LogisticRegressionModel,
    MLResult,
    MachineLearningPipeline,
)


class MachineLearningPipelineTests(TestCase):
    def setUp(self) -> None:
        start = timezone.now() - timedelta(hours=180)
        candles = []
        for index in range(180):
            wave = ((index % 12) - 6) * 0.8
            price = Decimal(str(100 + index * 0.05 + wave))
            candles.append(
                MarketCandle(
                    symbol="BTCUSDT",
                    resolution="60",
                    opened_at=start + timedelta(hours=index),
                    open_price=price,
                    high_price=price + 2,
                    low_price=price - 2,
                    close_price=price + Decimal("0.3"),
                    volume=Decimal(100 + (index % 20) * 5),
                )
            )
        MarketCandle.objects.bulk_create(candles)

    def test_feature_dataset_uses_future_horizon_label(self) -> None:
        rows = FeatureEngineeringService().build("BTCUSDT", horizon=3)

        self.assertGreater(len(rows), 100)
        self.assertEqual(MLFeatureRow.objects.count(), len(rows))
        self.assertEqual(
            set(rows[0].features),
            {
                "return_1",
                "return_5",
                "volatility_10",
                "volume_zscore_20",
                "range_fraction",
                "sma_gap",
                "rsi_14",
            },
        )

    def test_pipeline_trains_evaluates_and_records_drift(self) -> None:
        result: MLResult = MachineLearningPipeline().train("BTCUSDT", horizon=3)

        run = MLTrainingRun.objects.get(pk=result.run_id)
        self.assertEqual(run.status, MLTrainingRun.Status.COMPLETED)
        self.assertGreater(run.train_size, run.test_size)
        self.assertIn("accuracy", run.test_metrics)
        self.assertIn("auc", run.test_metrics)
        self.assertEqual(len(run.drift_report), 7)
        self.assertEqual(len(run.feature_importance), 7)
        self.assertGreaterEqual(result.latest_probability_up, 0)
        self.assertLessEqual(result.latest_probability_up, 1)

    def test_logistic_regression_learns_separable_data(self) -> None:
        x = [[-2.0], [-1.0], [1.0], [2.0]]
        y = [0, 0, 1, 1]
        model = LogisticRegressionModel()
        weights, bias = model.fit(x, y)
        probabilities = model.predict_probability(x, weights, bias)

        self.assertLess(probabilities[1], 0.5)
        self.assertGreater(probabilities[2], 0.5)
