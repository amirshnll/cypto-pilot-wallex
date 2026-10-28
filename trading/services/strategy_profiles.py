from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading.models import BotConfiguration

COMMODITY_BASE_ASSETS: frozenset[str] = frozenset(
    {
        "USOON",
        "UNGON",
        "PPLTON",
        "XAUT",
        "SLVON",
        "COPXON",
    }
)


def is_commodity_symbol(symbol: str) -> bool:
    normalized = symbol.replace("/", "").replace("-", "").upper()
    for quote in ("USDT", "TMN"):
        if normalized.endswith(quote):
            normalized = normalized[: -len(quote)]
            break
    return normalized in COMMODITY_BASE_ASSETS


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    asset_class: str
    fast_period: int
    slow_period: int
    rsi_period: int
    rsi_buy_ceiling: float
    rsi_sell_floor: float
    enabled_strategies: tuple[str, ...]
    strategy_weights: dict[str, float]
    consensus_threshold: float

    @property
    def engine_parameters(self) -> dict[str, int | float]:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "rsi_period": self.rsi_period,
            "rsi_buy_ceiling": self.rsi_buy_ceiling,
            "rsi_sell_floor": self.rsi_sell_floor,
        }


def profile_for(configuration: BotConfiguration, symbol: str) -> StrategyProfile:
    if is_commodity_symbol(symbol):
        return StrategyProfile(
            asset_class="commodity",
            fast_period=configuration.commodity_fast_period,
            slow_period=configuration.commodity_slow_period,
            rsi_period=configuration.commodity_rsi_period,
            rsi_buy_ceiling=float(configuration.commodity_rsi_buy_ceiling),
            rsi_sell_floor=float(configuration.commodity_rsi_sell_floor),
            enabled_strategies=tuple(configuration.commodity_enabled_strategies),
            strategy_weights={
                str(key): float(value)
                for key, value in configuration.commodity_strategy_weights.items()
            },
            consensus_threshold=float(configuration.commodity_consensus_threshold),
        )
    return StrategyProfile(
        asset_class="crypto",
        fast_period=configuration.fast_period,
        slow_period=configuration.slow_period,
        rsi_period=configuration.rsi_period,
        rsi_buy_ceiling=float(configuration.rsi_buy_ceiling),
        rsi_sell_floor=float(configuration.rsi_sell_floor),
        enabled_strategies=tuple(configuration.enabled_strategies),
        strategy_weights={
            str(key): float(value)
            for key, value in configuration.strategy_weights.items()
        },
        consensus_threshold=float(configuration.consensus_threshold),
    )
