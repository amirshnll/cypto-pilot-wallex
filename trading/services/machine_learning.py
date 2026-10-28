from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import exp, log
from statistics import fmean, pstdev

from django.utils import timezone

from trading.models import MLFeatureRow, MLTrainingRun, MarketCandle
from trading.services.analysis import TechnicalAnalysisService
from trading.services.candles import last_closed_open_time

FEATURE_NAMES: tuple[str, ...] = (
    "return_1",
    "return_5",
    "volatility_10",
    "volume_zscore_20",
    "range_fraction",
    "sma_gap",
    "rsi_14",
)


@dataclass(frozen=True, slots=True)
class MLResult:
    run_id: int
    symbol: str
    dataset_size: int
    test_accuracy: float
    test_f1: float
    test_auc: float
    drift_score: float
    drift_detected: bool
    latest_probability_up: float


class FeatureEngineeringService:
    def build(
        self, symbol: str, resolution: str = "60", horizon: int = 3
    ) -> list[MLFeatureRow]:
        candles = list(
            MarketCandle.objects.filter(
                symbol=symbol,
                resolution=resolution,
                opened_at__lte=last_closed_open_time(resolution),
            ).order_by("opened_at")
        )
        if len(candles) < 80:
            raise ValueError(
                f"{symbol} needs at least 80 candles; found {len(candles)}"
            )
        closes = [float(item.close_price) for item in candles]
        volumes = [float(item.volume) for item in candles]
        analysis = TechnicalAnalysisService()
        sma_fast = analysis.sma(closes, 5)
        sma_slow = analysis.sma(closes, 20)
        rsi = analysis.rsi(closes, 14)
        pending: list[MLFeatureRow] = []
        for index in range(20, len(candles) - horizon):
            returns_10 = [
                closes[pos] / closes[pos - 1] - 1 for pos in range(index - 9, index + 1)
            ]
            volume_window = volumes[index - 19 : index + 1]
            volume_deviation = pstdev(volume_window)
            features = {
                "return_1": closes[index] / closes[index - 1] - 1,
                "return_5": closes[index] / closes[index - 5] - 1,
                "volatility_10": pstdev(returns_10),
                "volume_zscore_20": (
                    (volumes[index] - fmean(volume_window)) / volume_deviation
                    if volume_deviation
                    else 0.0
                ),
                "range_fraction": (
                    float(candles[index].high_price) - float(candles[index].low_price)
                )
                / closes[index],
                "sma_gap": (
                    (sma_fast[index] or closes[index])
                    / (sma_slow[index] or closes[index])
                )
                - 1,
                "rsi_14": ((rsi[index] or 50.0) - 50.0) / 50.0,
            }
            future_return = closes[index + horizon] / closes[index] - 1
            pending.append(
                MLFeatureRow(
                    symbol=symbol,
                    opened_at=candles[index].opened_at,
                    horizon=horizon,
                    features=features,
                    target_up=future_return > 0,
                    future_return=Decimal(str(future_return)),
                )
            )
        MLFeatureRow.objects.bulk_create(
            pending,
            update_conflicts=True,
            update_fields=("features", "target_up", "future_return"),
            unique_fields=("symbol", "opened_at", "horizon"),
        )
        return list(
            MLFeatureRow.objects.filter(symbol=symbol, horizon=horizon).order_by(
                "opened_at"
            )
        )


class LogisticRegressionModel:
    def fit(
        self,
        x: list[list[float]],
        y: list[int],
        iterations: int = 800,
        learning_rate: float = 0.08,
        l2: float = 0.01,
    ) -> tuple[list[float], float]:
        weights = [0.0] * len(x[0])
        bias = 0.0
        count = float(len(x))
        for _step in range(iterations):
            probabilities = [
                self._sigmoid(
                    sum(weight * value for weight, value in zip(weights, row)) + bias
                )
                for row in x
            ]
            errors = [
                probability - target for probability, target in zip(probabilities, y)
            ]
            for column in range(len(weights)):
                gradient = (
                    sum(error * row[column] for error, row in zip(errors, x)) / count
                    + l2 * weights[column]
                )
                weights[column] -= learning_rate * gradient
            bias -= learning_rate * sum(errors) / count
        return weights, bias

    @staticmethod
    def predict_probability(
        x: list[list[float]], weights: list[float], bias: float
    ) -> list[float]:
        return [
            LogisticRegressionModel._sigmoid(
                sum(weight * value for weight, value in zip(weights, row)) + bias
            )
            for row in x
        ]

    @staticmethod
    def _sigmoid(value: float) -> float:
        bounded = max(-35.0, min(35.0, value))
        return 1.0 / (1.0 + exp(-bounded))


class MachineLearningPipeline:
    def train(self, symbol: str, resolution: str = "60", horizon: int = 3) -> MLResult:
        run = MLTrainingRun.objects.create(
            symbol=symbol, horizon=horizon, feature_names=list(FEATURE_NAMES)
        )
        try:
            result = self._train(run, symbol, resolution, horizon)
        except Exception as exc:
            run.status = MLTrainingRun.Status.FAILED
            run.error = str(exc)
            run.completed_at = timezone.now()
            run.save(update_fields=("status", "error", "completed_at"))
            raise
        return result

    def _train(
        self, run: MLTrainingRun, symbol: str, resolution: str, horizon: int
    ) -> MLResult:
        rows = FeatureEngineeringService().build(symbol, resolution, horizon)
        if len(rows) < 50:
            raise ValueError("engineered dataset needs at least 50 rows")
        x = [[float(row.features[name]) for name in FEATURE_NAMES] for row in rows]
        y = [int(row.target_up) for row in rows]
        train_end = int(len(rows) * 0.60)
        validation_end = int(len(rows) * 0.80)

        train_x, train_y = x[: train_end - horizon], y[: train_end - horizon]
        validation_x, validation_y = (
            x[train_end : validation_end - horizon],
            y[train_end : validation_end - horizon],
        )
        test_x, test_y = x[validation_end:], y[validation_end:]
        means = [fmean(column) for column in zip(*train_x)]
        deviations = [pstdev(column) or 1.0 for column in zip(*train_x)]
        scale = lambda matrix: [
            [
                (value - means[index]) / deviations[index]
                for index, value in enumerate(row)
            ]
            for row in matrix
        ]
        train_scaled, validation_scaled, test_scaled = (
            scale(train_x),
            scale(validation_x),
            scale(test_x),
        )
        model = LogisticRegressionModel()
        weights, bias = model.fit(train_scaled, train_y)
        validation_probability = model.predict_probability(
            validation_scaled, weights, bias
        )
        test_probability = model.predict_probability(test_scaled, weights, bias)
        validation_metrics = self._metrics(validation_y, validation_probability)
        test_metrics = self._metrics(test_y, test_probability)
        drift_report = self._drift(train_x, test_x)
        drift_score = max(drift_report.values()) if drift_report else 0.0
        latest_probability = model.predict_probability(
            [scale([x[-1]])[0]], weights, bias
        )[0]
        run.status = MLTrainingRun.Status.COMPLETED
        run.dataset_size = len(rows)
        run.train_size = len(train_x)
        run.validation_size = len(validation_x)
        run.test_size = len(test_x)
        run.coefficients = {
            **{name: weights[index] for index, name in enumerate(FEATURE_NAMES)},
            "intercept": bias,
        }
        run.scaler = {
            name: {"mean": means[index], "std": deviations[index]}
            for index, name in enumerate(FEATURE_NAMES)
        }
        run.validation_metrics = validation_metrics
        run.test_metrics = test_metrics
        run.feature_importance = dict(
            sorted(
                {
                    name: abs(weights[index])
                    for index, name in enumerate(FEATURE_NAMES)
                }.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        run.drift_report = drift_report
        run.drift_score = Decimal(str(drift_score))
        run.drift_detected = drift_score >= 0.20
        run.latest_probability_up = Decimal(str(latest_probability))
        run.completed_at = timezone.now()
        run.save()
        return MLResult(
            run.pk,
            symbol,
            len(rows),
            test_metrics["accuracy"],
            test_metrics["f1"],
            test_metrics["auc"],
            drift_score,
            run.drift_detected,
            latest_probability,
        )

    @staticmethod
    def _metrics(y: list[int], probabilities: list[float]) -> dict[str, float | int]:
        predictions = [int(value >= 0.5) for value in probabilities]
        tp = sum(
            1 for actual, predicted in zip(y, predictions) if actual == predicted == 1
        )
        tn = sum(
            1 for actual, predicted in zip(y, predictions) if actual == predicted == 0
        )
        fp = sum(
            1
            for actual, predicted in zip(y, predictions)
            if actual == 0 and predicted == 1
        )
        fn = sum(
            1
            for actual, predicted in zip(y, predictions)
            if actual == 1 and predicted == 0
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return {
            "accuracy": (tp + tn) / len(y) if y else 0.0,
            "precision": precision,
            "recall": recall,
            "f1": (
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            ),
            "auc": MachineLearningPipeline._auc(y, probabilities),
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
        }

    @staticmethod
    def _auc(y: list[int], probabilities: list[float]) -> float:
        positives = [score for target, score in zip(y, probabilities) if target == 1]
        negatives = [score for target, score in zip(y, probabilities) if target == 0]
        if not positives or not negatives:
            return 0.5
        wins = sum(
            1.0 if positive > negative else 0.5 if positive == negative else 0.0
            for positive in positives
            for negative in negatives
        )
        return wins / (len(positives) * len(negatives))

    @staticmethod
    def _drift(
        train: list[list[float]], current: list[list[float]]
    ) -> dict[str, float]:
        report: dict[str, float] = {}
        for index, name in enumerate(FEATURE_NAMES):
            baseline = [row[index] for row in train]
            recent = [row[index] for row in current]
            low, high = min(baseline), max(baseline)
            width = (high - low) / 5 if high > low else 1.0
            psi = 0.0
            for bucket in range(5):
                left = low + bucket * width
                right = high if bucket == 4 else low + (bucket + 1) * width
                expected = max(
                    0.0001,
                    sum(
                        left <= value <= right if bucket == 4 else left <= value < right
                        for value in baseline
                    )
                    / len(baseline),
                )
                actual = max(
                    0.0001,
                    sum(
                        left <= value <= right if bucket == 4 else left <= value < right
                        for value in recent
                    )
                    / len(recent),
                )
                psi += (actual - expected) * log(actual / expected)
            report[name] = psi
        return report
