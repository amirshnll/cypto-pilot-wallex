from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from statistics import fmean, pstdev

from django.utils import timezone

from trading.models import (
    BotConfiguration,
    MarketCandle,
    MarketRegimeSnapshot,
    StrategyOptimizationRun,
)
from trading.services.analysis import TechnicalAnalysisService
from trading.services.strategies import StrategyEngine, StrategySignal
from trading.services.candles import last_closed_open_time


@dataclass(frozen=True, slots=True)
class SimulationScore:
    total_return: float
    maximum_drawdown: float
    trades: int


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    run_id: int
    symbol: str
    best_parameters: dict[str, object]
    train_return: float
    validation_return: float
    test_return: float
    overfit_gap: float
    stability_score: float
    market_regime: str


class MarketRegimeDetector:
    def detect(self, symbol: str, closes: list[float]) -> MarketRegimeSnapshot:
        if len(closes) < 30:
            raise ValueError("market regime detection needs at least 30 closes")
        analysis = TechnicalAnalysisService()
        fast: float = analysis.sma(closes, 10)[-1] or closes[-1]
        slow: float = analysis.sma(closes, 30)[-1] or closes[-1]
        trend: float = (fast - slow) / slow if slow else 0.0
        returns: list[float] = [
            current / previous - 1
            for previous, current in zip(closes, closes[1:])
            if previous
        ]
        volatility: float = pstdev(returns[-30:]) if len(returns) > 1 else 0.0
        if volatility > 0.025:
            regime = MarketRegimeSnapshot.Regime.VOLATILE
            confidence = min(1.0, volatility / 0.05)
        elif abs(trend) < 0.01:
            regime = MarketRegimeSnapshot.Regime.RANGING
            confidence = min(1.0, 1.0 - abs(trend) / 0.01)
        elif trend > 0:
            regime = MarketRegimeSnapshot.Regime.TREND_UP
            confidence = min(1.0, abs(trend) / 0.05)
        else:
            regime = MarketRegimeSnapshot.Regime.TREND_DOWN
            confidence = min(1.0, abs(trend) / 0.05)
        return MarketRegimeSnapshot.objects.create(
            symbol=symbol,
            regime=regime,
            trend_strength=Decimal(str(trend)),
            volatility=Decimal(str(volatility)),
            confidence=Decimal(str(confidence)),
        )


class StrategyOptimizationService:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.configuration = configuration
        self.engine = StrategyEngine()
        self.fee = float(configuration.paper_fee_fraction)
        self.slippage = float(configuration.paper_slippage_bps) / 10000.0

    def optimize(self, symbol: str, resolution: str = "60") -> OptimizationResult:
        candles = list(
            MarketCandle.objects.filter(
                symbol=symbol,
                resolution=resolution,
                opened_at__lte=last_closed_open_time(resolution),
            ).order_by("opened_at")
        )
        if len(candles) < 120:
            raise ValueError(
                f"{symbol} needs at least 120 candles; found {len(candles)}"
            )
        run = StrategyOptimizationRun.objects.create(
            symbol=symbol, resolution=resolution, candle_count=len(candles)
        )
        try:
            result = self._optimize(run, symbol, candles)
        except Exception as exc:
            run.status = StrategyOptimizationRun.Status.FAILED
            run.error = str(exc)
            run.completed_at = timezone.now()
            run.save(update_fields=("status", "error", "completed_at"))
            raise
        return result

    def _optimize(
        self, run: StrategyOptimizationRun, symbol: str, candles: list[MarketCandle]
    ) -> OptimizationResult:
        closes = [float(c.close_price) for c in candles]
        train_end = int(len(candles) * 0.60)
        validation_end = int(len(candles) * 0.80)
        regime = MarketRegimeDetector().detect(symbol, closes)
        candidates = self._candidates()
        ranked: list[
            tuple[float, dict[str, object], SimulationScore, SimulationScore]
        ] = []
        for parameters in candidates:
            train = self._simulate(candles, 35, train_end, parameters)
            validation = self._simulate(candles, train_end, validation_end, parameters)
            gap = abs(train.total_return - validation.total_return)
            score = (
                validation.total_return
                - gap * 0.50
                - validation.maximum_drawdown * 0.30
            )
            ranked.append((score, parameters, train, validation))
        ranked.sort(key=lambda item: item[0], reverse=True)
        _score, best, train, validation = ranked[0]
        test = self._simulate(candles, validation_end, len(candles), best)
        sensitivity = self._sensitivity(candles, train_end, validation_end, best)
        nearby_returns = [float(item["return"]) for item in sensitivity]
        dispersion = pstdev(nearby_returns) if len(nearby_returns) > 1 else 0.0
        stability = max(0.0, 1.0 - dispersion / (abs(validation.total_return) + 0.01))
        top = [
            {
                "score": score,
                "parameters": params,
                "train_return": tr.total_return,
                "validation_return": va.total_return,
                "drawdown": va.maximum_drawdown,
            }
            for score, params, tr, va in ranked[:10]
        ]
        run.status = StrategyOptimizationRun.Status.COMPLETED
        run.candidate_count = len(candidates)
        run.best_parameters = best
        run.train_return = Decimal(str(train.total_return))
        run.validation_return = Decimal(str(validation.total_return))
        run.test_return = Decimal(str(test.total_return))
        run.test_drawdown = Decimal(str(test.maximum_drawdown))
        run.overfit_gap = Decimal(
            str(abs(train.total_return - validation.total_return))
        )
        run.stability_score = Decimal(str(stability))
        run.market_regime = regime.regime
        run.sensitivity = sensitivity
        run.top_candidates = top
        run.completed_at = timezone.now()
        run.save()
        return OptimizationResult(
            run.pk,
            symbol,
            best,
            train.total_return,
            validation.total_return,
            test.total_return,
            abs(train.total_return - validation.total_return),
            stability,
            regime.regime,
        )

    def _candidates(self) -> list[dict[str, object]]:
        names = list(self.configuration.enabled_strategies)
        groups = [names] + [[name] for name in names]
        candidates: list[dict[str, object]] = []
        for enabled in groups:
            for threshold in (0.20, 0.35, 0.50):
                candidates.append(
                    {
                        "enabled_strategies": enabled,
                        "consensus_threshold": threshold,
                        "strategy_weights": {name: 1.0 for name in enabled},
                    }
                )
                for focus in enabled:
                    candidates.append(
                        {
                            "enabled_strategies": enabled,
                            "consensus_threshold": threshold,
                            "strategy_weights": {
                                name: 2.0 if name == focus else 1.0 for name in enabled
                            },
                        }
                    )
        return candidates

    def _sensitivity(
        self, candles: list[MarketCandle], start: int, end: int, best: dict[str, object]
    ) -> list[dict[str, float]]:
        base = float(best["consensus_threshold"])
        points: list[dict[str, float]] = []
        for threshold in sorted(
            {
                max(0.05, base - 0.10),
                max(0.05, base - 0.05),
                base,
                min(0.95, base + 0.05),
                min(0.95, base + 0.10),
            }
        ):
            parameters = {**best, "consensus_threshold": threshold}
            score = self._simulate(candles, start, end, parameters)
            points.append(
                {
                    "threshold": threshold,
                    "return": score.total_return,
                    "drawdown": score.maximum_drawdown,
                }
            )
        return points

    def _simulate(
        self,
        candles: list[MarketCandle],
        start: int,
        end: int,
        parameters: dict[str, object],
    ) -> SimulationScore:
        cash, quantity, peak, drawdown, trades = 1.0, 0.0, 1.0, 0.0, 0
        for index in range(start, end):
            closes = [float(item.close_price) for item in candles[:index]]
            signal, _confidence, _reason, _parts = self.engine.evaluate(closes, parameters["enabled_strategies"], parameters["strategy_weights"], float(parameters["consensus_threshold"]))
            price = float(candles[index].open_price)
            if signal is StrategySignal.BUY and quantity == 0:
                quantity = cash / (price * (1 + self.slippage) * (1 + self.fee))
                cash = 0.0
                trades += 1
            elif signal is StrategySignal.SELL and quantity > 0:
                cash = quantity * price * (1 - self.slippage) * (1 - self.fee)
                quantity = 0.0
                trades += 1
            equity = cash + quantity * float(candles[index].close_price)
            peak = max(peak, equity)
            drawdown = max(drawdown, (peak - equity) / peak if peak else 0.0)
        final = cash + quantity * float(candles[end - 1].close_price)
        return SimulationScore(final - 1.0, drawdown, trades)
