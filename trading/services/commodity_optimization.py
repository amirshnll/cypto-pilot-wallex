from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from statistics import fmean

from trading.models import BotConfiguration, MarketCandle
from trading.services.candles import last_closed_open_time
from trading.services.strategies import StrategyEngine, StrategySignal
from trading.services.strategy_profiles import is_commodity_symbol, profile_for


@dataclass(frozen=True, slots=True)
class FoldScore:
    symbol: str
    fold: int
    total_return: float
    maximum_drawdown: float
    trades: int


@dataclass(frozen=True, slots=True)
class CommodityOptimizationResult:
    parameters: dict[str, object]
    score: float
    baseline_score: float
    eligible_symbols: tuple[str, ...]
    folds: tuple[FoldScore, ...]
    candidate_count: int


class CommodityWalkForwardOptimizer:
    MINIMUM_CANDLES = 240
    TRAIN_SIZE = 120
    TEST_SIZE = 48

    def __init__(self, configuration: BotConfiguration) -> None:
        self.configuration = configuration
        self.engine = StrategyEngine()
        self.fee = float(configuration.paper_fee_fraction)
        self.slippage = float(configuration.paper_slippage_bps) / 10000.0

    def optimize(
        self, symbols: tuple[str, ...], *, apply: bool = False
    ) -> CommodityOptimizationResult:
        datasets = {
            symbol: list(
                MarketCandle.objects.filter(
                    symbol=symbol,
                    resolution="60",
                    opened_at__lte=last_closed_open_time("60"),
                ).order_by("opened_at")
            )
            for symbol in symbols
            if is_commodity_symbol(symbol)
        }
        datasets = {
            symbol: candles
            for symbol, candles in datasets.items()
            if len(candles) >= self.MINIMUM_CANDLES
        }
        if not datasets:
            raise ValueError(
                f"no commodity has at least {self.MINIMUM_CANDLES} closed candles"
            )
        candidates = self._candidates()
        ranked: list[tuple[float, dict[str, object], tuple[FoldScore, ...]]] = []
        for candidate in candidates:
            folds = self._walk_forward(datasets, candidate)
            ranked.append((self._score(folds), candidate, folds))
        ranked.sort(key=lambda item: item[0], reverse=True)
        score, best, folds = ranked[0]
        baseline = self._profile_parameters()
        baseline_folds = self._walk_forward(datasets, baseline)
        baseline_score = self._score(baseline_folds)
        if baseline_score >= score:
            score, best, folds = baseline_score, baseline, baseline_folds
        result = CommodityOptimizationResult(
            parameters=best,
            score=score,
            baseline_score=baseline_score,
            eligible_symbols=tuple(sorted(datasets)),
            folds=folds,
            candidate_count=len(candidates),
        )
        if apply:
            self._apply(result)
        return result

    def _profile_parameters(self) -> dict[str, object]:
        profile = profile_for(self.configuration, "XAUTTMN")
        return {
            "enabled_strategies": list(profile.enabled_strategies),
            "strategy_weights": profile.strategy_weights,
            "consensus_threshold": profile.consensus_threshold,
            "fast_period": profile.fast_period,
            "slow_period": profile.slow_period,
            "rsi_period": profile.rsi_period,
            "rsi_buy_ceiling": profile.rsi_buy_ceiling,
            "rsi_sell_floor": profile.rsi_sell_floor,
        }

    def _candidates(self) -> list[dict[str, object]]:
        groups = (
            ("momentum",),
            ("macd",),
            ("breakout",),
            ("sma_rsi",),
            ("momentum", "macd", "breakout"),
            ("sma_rsi", "momentum", "macd", "breakout"),
            ("sma_rsi", "momentum", "macd", "bollinger", "breakout"),
        )
        period_sets = ((3, 12, 7), (5, 20, 14), (8, 30, 14))
        candidates: list[dict[str, object]] = []
        for enabled in groups:
            weight_sets = [{name: 1.0 for name in enabled}]
            weight_sets += [
                {name: 2.0 if name == focus else 1.0 for name in enabled}
                for focus in enabled
            ]
            for fast, slow, rsi in period_sets:
                for threshold in (0.35, 0.50, 0.65):
                    for weights in weight_sets:
                        candidates.append(
                            {
                                "enabled_strategies": list(enabled),
                                "strategy_weights": weights,
                                "consensus_threshold": threshold,
                                "fast_period": fast,
                                "slow_period": slow,
                                "rsi_period": rsi,
                                "rsi_buy_ceiling": 65.0,
                                "rsi_sell_floor": 70.0,
                            }
                        )
        return candidates

    def _walk_forward(
        self,
        datasets: dict[str, list[MarketCandle]],
        parameters: dict[str, object],
    ) -> tuple[FoldScore, ...]:
        scores: list[FoldScore] = []
        for symbol, candles in datasets.items():
            fold = 0
            cursor = self.TRAIN_SIZE
            while cursor < len(candles):
                end = min(cursor + self.TEST_SIZE, len(candles))
                fold += 1
                scores.append(
                    self._simulate(symbol, fold, candles, cursor, end, parameters)
                )
                cursor = end
        return tuple(scores)

    def _simulate(
        self,
        symbol: str,
        fold: int,
        candles: list[MarketCandle],
        start: int,
        end: int,
        parameters: dict[str, object],
    ) -> FoldScore:
        cash, quantity = 1.0, 0.0
        peak, drawdown, trades = 1.0, 0.0, 0
        strategy_parameters = {
            key: parameters[key]
            for key in (
                "fast_period",
                "slow_period",
                "rsi_period",
                "rsi_buy_ceiling",
                "rsi_sell_floor",
            )
        }
        for index in range(start, end):
            closes = [float(item.close_price) for item in candles[:index]]
            signal, _confidence, _reason, _parts = self.engine.evaluate(
                closes,
                parameters["enabled_strategies"],
                parameters["strategy_weights"],
                float(parameters["consensus_threshold"]),
                strategy_parameters,
            )
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
        return FoldScore(symbol, fold, final - 1.0, drawdown, trades)

    @staticmethod
    def _score(folds: tuple[FoldScore, ...]) -> float:
        minimum_active_folds = max(3, len(folds) // 3)
        active_folds = sum(item.trades > 0 for item in folds)
        if active_folds < minimum_active_folds:
            return -1.0
        returns = [item.total_return for item in folds]
        drawdowns = [item.maximum_drawdown for item in folds]
        inactive = sum(item.trades == 0 for item in folds) / len(folds)
        return fmean(returns) - 0.50 * fmean(drawdowns) - 0.03 * inactive

    def _apply(self, result: CommodityOptimizationResult) -> None:
        p = result.parameters
        self.configuration.commodity_enabled_strategies = p["enabled_strategies"]
        self.configuration.commodity_strategy_weights = p["strategy_weights"]
        self.configuration.commodity_consensus_threshold = Decimal(
            str(p["consensus_threshold"])
        )
        self.configuration.commodity_fast_period = int(p["fast_period"])
        self.configuration.commodity_slow_period = int(p["slow_period"])
        self.configuration.commodity_rsi_period = int(p["rsi_period"])
        self.configuration.commodity_rsi_buy_ceiling = Decimal(
            str(p["rsi_buy_ceiling"])
        )
        self.configuration.commodity_rsi_sell_floor = Decimal(str(p["rsi_sell_floor"]))
        self.configuration.commodity_optimization_report = {
            "method": "expanding-history walk-forward",
            "minimum_candles": self.MINIMUM_CANDLES,
            "train_size": self.TRAIN_SIZE,
            "test_size": self.TEST_SIZE,
            "candidate_count": result.candidate_count,
            "eligible_symbols": list(result.eligible_symbols),
            "score": result.score,
            "baseline_score": result.baseline_score,
            "parameters": result.parameters,
            "folds": [asdict(item) for item in result.folds],
        }
        self.configuration.save(
            update_fields=(
                "commodity_enabled_strategies",
                "commodity_strategy_weights",
                "commodity_consensus_threshold",
                "commodity_fast_period",
                "commodity_slow_period",
                "commodity_rsi_period",
                "commodity_rsi_buy_ceiling",
                "commodity_rsi_sell_floor",
                "commodity_optimization_report",
                "updated_at",
            )
        )
