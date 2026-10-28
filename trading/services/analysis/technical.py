from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence, TypeAlias

Number: TypeAlias = int | float


@dataclass(frozen=True, slots=True)
class DescriptiveStatistics:
    count: int
    mean: float
    median: float
    minimum: float
    maximum: float
    variance: float
    standard_deviation: float
    skewness: float
    excess_kurtosis: float


@dataclass(frozen=True, slots=True)
class BollingerBands:
    middle: tuple[float | None, ...]
    upper: tuple[float | None, ...]
    lower: tuple[float | None, ...]


@dataclass(frozen=True, slots=True)
class RiskMetrics:
    cumulative_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    maximum_drawdown: float


class TechnicalAnalysisService:
    @staticmethod
    def _values(
        values: Sequence[Number], *, minimum_length: int = 1
    ) -> tuple[float, ...]:
        normalized: tuple[float, ...] = tuple(float(value) for value in values)
        if len(normalized) < minimum_length:
            raise ValueError(f"at least {minimum_length} values are required")
        if any(not math.isfinite(value) for value in normalized):
            raise ValueError("values must be finite numbers")
        return normalized

    @staticmethod
    def _period(period: int) -> int:
        if isinstance(period, bool) or period <= 0:
            raise ValueError("period must be a positive integer")
        return period

    def descriptive_statistics(self, values: Sequence[Number]) -> DescriptiveStatistics:
        data: tuple[float, ...] = self._values(values)
        count: int = len(data)
        mean: float = statistics.fmean(data)
        variance: float = statistics.pvariance(data)
        standard_deviation: float = math.sqrt(variance)

        if standard_deviation == 0.0:
            skewness: float = 0.0
            excess_kurtosis: float = 0.0
        else:
            standardized: tuple[float, ...] = tuple(
                (value - mean) / standard_deviation for value in data
            )
            skewness = statistics.fmean(value**3 for value in standardized)
            excess_kurtosis = statistics.fmean(value**4 for value in standardized) - 3.0

        return DescriptiveStatistics(
            count=count,
            mean=mean,
            median=statistics.median(data),
            minimum=min(data),
            maximum=max(data),
            variance=variance,
            standard_deviation=standard_deviation,
            skewness=skewness,
            excess_kurtosis=excess_kurtosis,
        )

    def simple_returns(self, prices: Sequence[Number]) -> tuple[float, ...]:
        data: tuple[float, ...] = self._values(prices, minimum_length=2)
        if any(price == 0.0 for price in data[:-1]):
            raise ValueError("a previous price cannot be zero")
        return tuple(
            data[index] / data[index - 1] - 1.0 for index in range(1, len(data))
        )

    def logarithmic_returns(self, prices: Sequence[Number]) -> tuple[float, ...]:
        data: tuple[float, ...] = self._values(prices, minimum_length=2)
        if any(price <= 0.0 for price in data):
            raise ValueError("prices must be positive for logarithmic returns")
        return tuple(
            math.log(data[index] / data[index - 1]) for index in range(1, len(data))
        )

    def sma(self, values: Sequence[Number], period: int) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        running_sum: float = 0.0
        for index, value in enumerate(data):
            running_sum += value
            if index >= window:
                running_sum -= data[index - window]
            if index >= window - 1:
                result[index] = running_sum / window
        return tuple(result)

    def ema(self, values: Sequence[Number], period: int) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        if len(data) < window:
            return tuple(result)
        previous: float = statistics.fmean(data[:window])
        result[window - 1] = previous
        multiplier: float = 2.0 / (window + 1.0)
        for index in range(window, len(data)):
            previous = (data[index] - previous) * multiplier + previous
            result[index] = previous
        return tuple(result)

    def wma(self, values: Sequence[Number], period: int) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        denominator: float = window * (window + 1) / 2
        result: list[float | None] = [None] * len(data)
        for index in range(window - 1, len(data)):
            segment: tuple[float, ...] = data[index - window + 1 : index + 1]
            result[index] = (
                sum(value * weight for weight, value in enumerate(segment, 1))
                / denominator
            )
        return tuple(result)

    def momentum(
        self, values: Sequence[Number], period: int = 1
    ) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        for index in range(window, len(data)):
            result[index] = data[index] - data[index - window]
        return tuple(result)

    def rate_of_change(
        self, values: Sequence[Number], period: int = 1
    ) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        for index in range(window, len(data)):
            previous: float = data[index - window]
            if previous == 0.0:
                raise ValueError("a previous value cannot be zero")
            result[index] = (data[index] / previous - 1.0) * 100.0
        return tuple(result)

    def z_scores(
        self, values: Sequence[Number], period: int
    ) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(values)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        for index in range(window - 1, len(data)):
            segment: tuple[float, ...] = data[index - window + 1 : index + 1]
            mean: float = statistics.fmean(segment)
            deviation: float = statistics.pstdev(segment)
            result[index] = (
                0.0 if deviation == 0.0 else (data[index] - mean) / deviation
            )
        return tuple(result)

    def rsi(
        self, prices: Sequence[Number], period: int = 14
    ) -> tuple[float | None, ...]:
        data: tuple[float, ...] = self._values(prices)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(data)
        if len(data) <= window:
            return tuple(result)
        changes: tuple[float, ...] = tuple(
            data[i] - data[i - 1] for i in range(1, len(data))
        )
        average_gain: float = statistics.fmean(
            max(change, 0.0) for change in changes[:window]
        )
        average_loss: float = statistics.fmean(
            max(-change, 0.0) for change in changes[:window]
        )
        result[window] = self._rsi_value(average_gain, average_loss)
        for change_index in range(window, len(changes)):
            gain: float = max(changes[change_index], 0.0)
            loss: float = max(-changes[change_index], 0.0)
            average_gain = ((window - 1) * average_gain + gain) / window
            average_loss = ((window - 1) * average_loss + loss) / window
            result[change_index + 1] = self._rsi_value(average_gain, average_loss)
        return tuple(result)

    @staticmethod
    def _rsi_value(average_gain: float, average_loss: float) -> float:
        if average_loss == 0.0:
            return 100.0 if average_gain > 0.0 else 50.0
        relative_strength: float = average_gain / average_loss
        return 100.0 - (100.0 / (1.0 + relative_strength))

    def bollinger_bands(
        self,
        prices: Sequence[Number],
        period: int = 20,
        standard_deviations: float = 2.0,
    ) -> BollingerBands:
        data: tuple[float, ...] = self._values(prices)
        window: int = self._period(period)
        if standard_deviations <= 0.0:
            raise ValueError("standard_deviations must be positive")
        middle: list[float | None] = list(self.sma(data, window))
        upper: list[float | None] = [None] * len(data)
        lower: list[float | None] = [None] * len(data)
        for index in range(window - 1, len(data)):
            segment: tuple[float, ...] = data[index - window + 1 : index + 1]
            deviation: float = statistics.pstdev(segment)
            center: float = middle[index]
            upper[index] = center + standard_deviations * deviation
            lower[index] = center - standard_deviations * deviation
        return BollingerBands(tuple(middle), tuple(upper), tuple(lower))

    def true_range(
        self,
        highs: Sequence[Number],
        lows: Sequence[Number],
        closes: Sequence[Number],
    ) -> tuple[float, ...]:
        high_values: tuple[float, ...] = self._values(highs)
        low_values: tuple[float, ...] = self._values(lows)
        close_values: tuple[float, ...] = self._values(closes)
        if not (len(high_values) == len(low_values) == len(close_values)):
            raise ValueError("highs, lows, and closes must have equal lengths")
        result: list[float] = [high_values[0] - low_values[0]]
        for index in range(1, len(close_values)):
            result.append(
                max(
                    high_values[index] - low_values[index],
                    abs(high_values[index] - close_values[index - 1]),
                    abs(low_values[index] - close_values[index - 1]),
                )
            )
        return tuple(result)

    def atr(
        self,
        highs: Sequence[Number],
        lows: Sequence[Number],
        closes: Sequence[Number],
        period: int = 14,
    ) -> tuple[float | None, ...]:
        ranges: tuple[float, ...] = self.true_range(highs, lows, closes)
        window: int = self._period(period)
        result: list[float | None] = [None] * len(ranges)
        if len(ranges) < window:
            return tuple(result)
        previous: float = statistics.fmean(ranges[:window])
        result[window - 1] = previous
        for index in range(window, len(ranges)):
            previous = ((window - 1) * previous + ranges[index]) / window
            result[index] = previous
        return tuple(result)

    def covariance(self, first: Sequence[Number], second: Sequence[Number]) -> float:
        left: tuple[float, ...] = self._values(first, minimum_length=2)
        right: tuple[float, ...] = self._values(second, minimum_length=2)
        if len(left) != len(right):
            raise ValueError("both series must have equal lengths")
        return statistics.covariance(left, right)

    def pearson_correlation(
        self, first: Sequence[Number], second: Sequence[Number]
    ) -> float:
        left: tuple[float, ...] = self._values(first, minimum_length=2)
        right: tuple[float, ...] = self._values(second, minimum_length=2)
        if len(left) != len(right):
            raise ValueError("both series must have equal lengths")
        try:
            return statistics.correlation(left, right)
        except statistics.StatisticsError as exc:
            raise ValueError("correlation requires non-constant series") from exc

    def maximum_drawdown(self, equity_curve: Sequence[Number]) -> float:
        equity: tuple[float, ...] = self._values(equity_curve)
        if any(value <= 0.0 for value in equity):
            raise ValueError("equity values must be positive")
        peak: float = equity[0]
        maximum: float = 0.0
        for value in equity:
            peak = max(peak, value)
            maximum = min(maximum, value / peak - 1.0)
        return maximum

    def risk_metrics(
        self,
        returns: Sequence[Number],
        *,
        periods_per_year: int = 365,
        risk_free_rate: float = 0.0,
    ) -> RiskMetrics:
        data: tuple[float, ...] = self._values(returns, minimum_length=2)
        periods: int = self._period(periods_per_year)
        cumulative: float = math.prod(1.0 + value for value in data) - 1.0
        if any(value <= -1.0 for value in data):
            annualized_return: float = -1.0
        else:
            annualized_return = (1.0 + cumulative) ** (periods / len(data)) - 1.0
        period_volatility: float = statistics.stdev(data)
        annualized_volatility: float = period_volatility * math.sqrt(periods)
        excess_mean: float = statistics.fmean(data) - risk_free_rate / periods
        sharpe: float | None = (
            None
            if period_volatility == 0.0
            else excess_mean / period_volatility * math.sqrt(periods)
        )
        downside: tuple[float, ...] = tuple(
            min(value - risk_free_rate / periods, 0.0) for value in data
        )
        downside_deviation: float = math.sqrt(
            statistics.fmean(value**2 for value in downside)
        )
        sortino: float | None = (
            None
            if downside_deviation == 0.0
            else excess_mean / downside_deviation * math.sqrt(periods)
        )
        equity: list[float] = [1.0]
        for value in data:
            equity.append(equity[-1] * (1.0 + value))
        return RiskMetrics(
            cumulative_return=cumulative,
            annualized_return=annualized_return,
            annualized_volatility=annualized_volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            maximum_drawdown=self.maximum_drawdown(equity),
        )

    def fixed_fractional_position_size(
        self,
        account_equity: Number,
        risk_fraction: Number,
        entry_price: Number,
        stop_price: Number,
    ) -> float:
        equity: float = float(account_equity)
        fraction: float = float(risk_fraction)
        entry: float = float(entry_price)
        stop: float = float(stop_price)
        if equity <= 0.0 or not 0.0 < fraction <= 1.0:
            raise ValueError(
                "equity must be positive and risk_fraction must be in (0, 1]"
            )
        risk_per_unit: float = abs(entry - stop)
        if risk_per_unit == 0.0:
            raise ValueError("entry_price and stop_price must differ")
        return equity * fraction / risk_per_unit
