from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Sequence

from trading.services.analysis import TechnicalAnalysisService


class StrategySignal(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    strategy: str
    signal: StrategySignal
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, str | float]:
        return asdict(self)


class TradingStrategy(ABC):
    name: str
    minimum_history: int

    def __init__(
        self,
        analysis: TechnicalAnalysisService,
        parameters: dict[str, int | float] | None = None,
    ) -> None:
        self.analysis = analysis
        self.parameters = parameters or {}

    @abstractmethod
    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        pass

class SmaRsiStrategy(TradingStrategy):
    name = "sma_rsi"
    minimum_history = 20

    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        fast_period = int(self.parameters.get("fast_period", 5))
        slow_period = int(self.parameters.get("slow_period", 20))
        rsi_period = int(self.parameters.get("rsi_period", 14))
        buy_ceiling = float(self.parameters.get("rsi_buy_ceiling", 70.0))
        sell_floor = float(self.parameters.get("rsi_sell_floor", 70.0))
        fast: float = self.analysis.sma(closes, fast_period)[-1] or 0.0
        slow: float = self.analysis.sma(closes, slow_period)[-1] or 0.0
        rsi_value: float | None = self.analysis.rsi(closes, rsi_period)[-1]
        rsi: float = 50.0 if rsi_value is None else rsi_value
        gap: float = abs(fast - slow) / slow if slow else 0.0
        confidence: float = min(1.0, gap * 100.0)
        if fast > slow and rsi < buy_ceiling:
            return StrategyDecision(
                self.name,
                StrategySignal.BUY,
                confidence,
                f"fast SMA > slow SMA; RSI={rsi:.1f}",
            )
        if fast < slow or rsi > sell_floor:
            return StrategyDecision(
                self.name,
                StrategySignal.SELL,
                confidence,
                f"fast SMA < slow SMA or RSI={rsi:.1f}",
            )
        return StrategyDecision(
            self.name,
            StrategySignal.HOLD,
            confidence,
            f"no confirmation; RSI={rsi:.1f}",
        )


class MomentumStrategy(TradingStrategy):
    name = "momentum"
    minimum_history = 11

    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        roc: float = self.analysis.rate_of_change(closes, 10)[-1] or 0.0
        confidence: float = min(1.0, abs(roc) / 5.0)
        signal: StrategySignal = (
            StrategySignal.BUY
            if roc > 0
            else StrategySignal.SELL if roc < 0 else StrategySignal.HOLD
        )
        return StrategyDecision(
            self.name, signal, confidence, f"10-period ROC={roc:.3f}%"
        )


class MacdStrategy(TradingStrategy):
    name = "macd"
    minimum_history = 35

    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        fast_values = self.analysis.ema(closes, 12)
        slow_values = self.analysis.ema(closes, 26)
        macd_values: list[float] = [
            fast - slow
            for fast, slow in zip(fast_values, slow_values, strict=True)
            if fast is not None and slow is not None
        ]
        macd: float = macd_values[-1]
        signal_line: float = self.analysis.ema(macd_values, 9)[-1] or 0.0
        histogram: float = macd - signal_line
        scale: float = abs(macd) + abs(signal_line)
        confidence: float = min(1.0, abs(histogram) / scale * 5.0) if scale else 0.0
        signal = (
            StrategySignal.BUY
            if histogram > 0
            else StrategySignal.SELL if histogram < 0 else StrategySignal.HOLD
        )
        return StrategyDecision(
            self.name, signal, confidence, f"MACD histogram={histogram:.8g}"
        )


class BollingerStrategy(TradingStrategy):
    name = "bollinger"
    minimum_history = 20

    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        bands = self.analysis.bollinger_bands(closes, 20, 2.0)
        price: float = closes[-1]
        upper: float = bands.upper[-1] or price
        lower: float = bands.lower[-1] or price
        width: float = upper - lower
        if price < lower:
            return StrategyDecision(
                self.name,
                StrategySignal.BUY,
                min(1.0, (lower - price) / width * 4) if width else 0.0,
                "price below lower band",
            )
        if price > upper:
            return StrategyDecision(
                self.name,
                StrategySignal.SELL,
                min(1.0, (price - upper) / width * 4) if width else 0.0,
                "price above upper band",
            )
        return StrategyDecision(
            self.name, StrategySignal.HOLD, 0.25, "price inside Bollinger bands"
        )


class BreakoutStrategy(TradingStrategy):
    name = "breakout"
    minimum_history = 21

    def evaluate(self, closes: Sequence[float]) -> StrategyDecision:
        price: float = closes[-1]
        window: Sequence[float] = closes[-21:-1]
        high: float = max(window)
        low: float = min(window)
        if price > high:
            return StrategyDecision(
                self.name,
                StrategySignal.BUY,
                min(1.0, (price / high - 1) * 100),
                "20-period upside breakout",
            )
        if price < low:
            return StrategyDecision(
                self.name,
                StrategySignal.SELL,
                min(1.0, (1 - price / low) * 100),
                "20-period downside breakout",
            )
        return StrategyDecision(
            self.name, StrategySignal.HOLD, 0.2, "price remains inside 20-period range"
        )


class StrategyEngine:
    STRATEGIES: dict[str, type[TradingStrategy]] = {
        "sma_rsi": SmaRsiStrategy,
        "momentum": MomentumStrategy,
        "macd": MacdStrategy,
        "bollinger": BollingerStrategy,
        "breakout": BreakoutStrategy,
    }

    def __init__(self, analysis: TechnicalAnalysisService | None = None) -> None:
        self.analysis = analysis or TechnicalAnalysisService()

    def evaluate(
        self,
        closes: Sequence[float],
        enabled: Sequence[str],
        weights: dict[str, float],
        consensus_threshold: float,
        strategy_parameters: dict[str, int | float] | None = None,
    ) -> tuple[StrategySignal, float, str, tuple[StrategyDecision, ...]]:
        decisions: list[StrategyDecision] = []
        for name in enabled:
            strategy_type = self.STRATEGIES.get(name)
            if strategy_type is None:
                continue
            strategy = strategy_type(self.analysis, strategy_parameters)
            minimum_history = strategy.minimum_history
            if name == "sma_rsi" and strategy_parameters:
                minimum_history = max(
                    minimum_history,
                    int(strategy_parameters.get("slow_period", 20)),
                    int(strategy_parameters.get("rsi_period", 14)) + 1,
                )
            if len(closes) < minimum_history:
                decisions.append(
                    StrategyDecision(
                        name,
                        StrategySignal.HOLD,
                        0.0,
                        f"warm-up: {len(closes)}/{minimum_history}",
                    )
                )
            else:
                decisions.append(strategy.evaluate(closes))
        if not decisions:
            return StrategySignal.HOLD, 0.0, "no enabled strategy", ()
        scores: dict[StrategySignal, float] = {signal: 0.0 for signal in StrategySignal}
        total_weight: float = 0.0
        for decision in decisions:
            weight: float = max(0.0, float(weights.get(decision.strategy, 1.0)))
            scores[decision.signal] += weight * max(0.1, decision.confidence)
            total_weight += weight
        winner: StrategySignal = max(scores, key=scores.get)
        confidence: float = scores[winner] / total_weight if total_weight else 0.0
        
        if sum(abs(score - scores[winner]) <= 1e-12 for score in scores.values()) > 1:
            winner = StrategySignal.HOLD
        if winner is StrategySignal.HOLD or confidence < consensus_threshold:
            winner = StrategySignal.HOLD
        summary: str = "; ".join(
            f"{item.strategy}={item.signal.value}" for item in decisions
        )
        return winner, min(1.0, confidence), summary, tuple(decisions)
