from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading.models import BotConfiguration
from trading.services.strategy_profiles import is_commodity_symbol

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class Exposure:
    symbol: str
    value: Decimal
    stop_risk: Decimal


@dataclass(frozen=True)
class EntryBudget:
    cash: Decimal
    reason: str


class TradePolicy:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.config = configuration

    def budget(
        self,
        symbol: str,
        cash: Decimal,
        equity: Decimal,
        confidence: Decimal,
        exposures: list[Exposure],
    ) -> EntryBudget:
        c = self.config
        if equity <= 0 or cash <= 0 or c.stop_loss_fraction <= 0:
            return EntryBudget(ZERO, "positive equity and a stop-loss are required")
        if len(exposures) >= c.maximum_open_positions:
            return EntryBudget(ZERO, "maximum open positions reached")
        commodity = is_commodity_symbol(symbol)
        group_value = sum(
            (p.value for p in exposures if is_commodity_symbol(p.symbol) == commodity),
            ZERO,
        )
        cap = (
            c.commodity_allocation_cap_fraction
            if commodity
            else c.maximum_crypto_allocation_fraction
        )
        cost_rate = (
            c.paper_fee_fraction * 2 + c.paper_slippage_bps / Decimal("10000") * 2
        )
        loss_rate = c.stop_loss_fraction + cost_rate
        open_risk = sum((p.stop_risk for p in exposures), ZERO)
        remaining_risk = max(ZERO, equity * c.maximum_total_risk_fraction - open_risk)
        multiplier = {"low": Decimal("0.5"), "medium": ONE, "high": Decimal("1.5")}.get(
            c.risk_level, ONE
        )
        signal_strength = min(ONE, max(ZERO, confidence))
        notional = min(
            cash / (ONE + c.paper_fee_fraction),
            equity * c.maximum_symbol_allocation_fraction,
            max(ZERO, equity * cap - group_value),
            equity
            * c.risk_per_trade_fraction
            * multiplier
            * signal_strength
            / loss_rate,
            remaining_risk / loss_rate,
        )
        budget = max(ZERO, notional * (ONE + c.paper_fee_fraction))
        minimum = c.minimum_order_tmn if symbol.endswith("TMN") else ZERO
        if notional < minimum or budget <= 0:
            return EntryBudget(
                ZERO, "entry budget below minimum order or risk capacity exhausted"
            )
        return EntryBudget(budget, "risk-sized entry")

    def exit_reason(
        self,
        price: Decimal,
        stop: Decimal | None,
        target: Decimal | None,
        trailing: Decimal | None,
    ) -> str | None:
        if stop is not None and price <= stop:
            return "stop-loss triggered"
        if target is not None and price >= target:
            return "take-profit triggered"
        if trailing is not None and price <= trailing:
            return "trailing stop triggered"
        return None
