from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal as D

from django.conf import settings

from trading.models import BotConfiguration, MarketCandle
from trading.services.entry_research import FilterVariant, entry_allowed
from trading.services.strategies import StrategyEngine, StrategySignal
from trading.services.strategy_profiles import profile_for
from trading.services.trade_policy import Exposure, TradePolicy


@dataclass
class ResearchPosition:
    quantity: D
    entry: D
    cost: D
    highest: D


def replay(
    config: BotConfiguration,
    datasets: dict[str, list[MarketCandle]],
    start: datetime,
    end: datetime,
    variant: FilterVariant,
    spread_bps: D = D("10"),
    cost_multiplier: D = D("1"),
    signal_cache: dict | None = None,
) -> dict[str, object]:
    policy = TradePolicy(config)
    engine = StrategyEngine()
    cache = {} if signal_cache is None else signal_cache
    indexes = {
        s: {c.opened_at: i for i, c in enumerate(cs)} for s, cs in datasets.items()
    }
    timeline = sorted({t for ix in indexes.values() for t in ix if start <= t <= end})
    initial = cash = peak = config.initial_tmn_balance
    dd = fees = exposure_sum = D("0")
    positions: dict[str, ResearchPosition] = {}
    marks: dict[str, D] = {}
    losses: Counter[str] = Counter()
    symbol_pnl: Counter[str] = Counter()
    halted_until: dict[str, datetime] = {}
    last_exit: dict[str, datetime] = {}
    pnls: list[D] = []
    pnl_by_symbol: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    buy_count = 0
    halted = False
    fee = config.paper_fee_fraction * cost_multiplier
    slip = (config.paper_slippage_bps + spread_bps / 2) / D("10000") * cost_multiplier

    def equity() -> D:
        return cash + sum((p.quantity * marks[s] for s, p in positions.items()), D("0"))

    def close(symbol: str, price: D, at: datetime) -> None:
        nonlocal cash, fees
        p = positions.pop(symbol)
        gross = p.quantity * price * (D("1") - slip)
        charge = gross * fee
        proceeds = gross - charge
        cash += proceeds
        fees += charge
        pnl = proceeds - p.cost
        pnls.append(pnl)
        pnl_by_symbol[symbol] += pnl
        symbol_pnl[symbol] += pnl
        losses[symbol] = losses[symbol] + 1 if pnl < 0 else 0
        if (
            losses[symbol] >= config.symbol_loss_streak_limit
            or symbol_pnl[symbol] <= -initial * config.symbol_loss_limit_fraction
        ):
            halted_until[symbol] = at + timedelta(days=config.symbol_halt_days)
        last_exit[symbol] = at

    for at in timeline:
        current = {
            s: cs[indexes[s][at]] for s, cs in datasets.items() if at in indexes[s]
        }
        for s, candle in current.items():
            marks[s] = candle.open_price
        peak = max(peak, equity())
        halted = halted or equity() <= peak * (
            D("1") - config.maximum_drawdown_fraction
        )
        signals = {}
        histories = {}
        for s, candle in current.items():
            i = indexes[s][at]
            history = datasets[s][max(0, i - 100) : i]
            if (
                len(history) < 100
                or history[-1].opened_at + timedelta(hours=1) != at
                or any(
                    b.opened_at - a.opened_at != timedelta(hours=1)
                    for a, b in zip(history, history[1:])
                )
            ):
                rejected["missing_or_gapped_hourly_history"] += 1
                continue
            profile = profile_for(config, s)
            key = (s, at)
            if key not in cache:
                cache[key] = engine.evaluate(
                    [float(c.close_price) for c in history],
                    profile.enabled_strategies,
                    profile.strategy_weights,
                    profile.consensus_threshold,
                    profile.engine_parameters,
                )
            signals[s] = cache[key]
            histories[s] = history

        for s in list(positions):
            if s not in current:
                continue
            p = positions[s]
            stop = p.entry * (D("1") - config.stop_loss_fraction)
            target = p.entry * (D("1") + config.take_profit_fraction)
            trailing = p.highest * (D("1") - config.trailing_stop_fraction)
            sell = s in signals and signals[s][0] == StrategySignal.SELL
            if sell or policy.exit_reason(
                current[s].open_price, stop, target, trailing
            ):
                close(s, current[s].open_price, at)

        for s in config.symbols:
            if (
                s in positions
                or s not in signals
                or signals[s][0] != StrategySignal.BUY
                or halted
            ):
                continue
            if s in halted_until:
                if at < halted_until[s]:
                    rejected["symbol_halt"] += 1
                    continue
                del halted_until[s]
                losses[s] = 0
                symbol_pnl[s] = D("0")
            if s in last_exit and at <= last_exit[s] + timedelta(
                minutes=settings.PAPER_REENTRY_COOLDOWN_MINUTES
            ):
                rejected["reentry_cooldown"] += 1
                continue
            allowed, reason = entry_allowed(
                histories[s], at, config, variant, spread_bps
            )
            if not allowed:
                rejected[reason] += 1
                continue
            exposures = []
            for ps, p in positions.items():
                value = p.quantity * marks[ps]
                stop = max(
                    p.entry * (1 - config.stop_loss_fraction),
                    p.highest * (1 - config.trailing_stop_fraction),
                )
                risk = max(D("0"), marks[ps] - stop) * p.quantity + value * (
                    2 * fee + 2 * slip
                )
                exposures.append(Exposure(ps, value, risk))
            budget = policy.budget(
                s, cash, equity(), D(str(signals[s][1])), exposures
            ).cash
            if budget <= 0:
                rejected["risk_or_minimum_budget"] += 1
                continue
            fill = current[s].open_price * (D("1") + slip)
            gross = budget / (1 + fee)
            if gross < config.minimum_order_tmn:
                rejected["minimum_order"] += 1
                continue
            positions[s] = ResearchPosition(gross / fill, fill, budget, fill)
            cash -= budget
            fees += gross * fee
            buy_count += 1

        for s in list(positions):
            if s not in current:
                continue
            p, candle = positions[s], current[s]
            stop = max(
                p.entry * (1 - config.stop_loss_fraction),
                p.highest * (1 - config.trailing_stop_fraction),
            )
            target = p.entry * (1 + config.take_profit_fraction)
            if candle.low_price <= stop:
                close(s, stop, at)
            elif candle.high_price >= target:
                close(s, target, at)
            else:
                p.highest = max(p.highest, candle.high_price)
        for s, candle in current.items():
            marks[s] = candle.close_price
        value = equity()
        peak = max(peak, value)
        dd = max(dd, (peak - value) / peak)
        halted = halted or dd >= config.maximum_drawdown_fraction
        exposure_sum += (value - cash) / value if value else D("0")

    profit = sum((p for p in pnls if p > 0), D("0"))
    loss = -sum((p for p in pnls if p < 0), D("0"))
    benchmark_returns = []
    for cs in datasets.values():
        available = [c for c in cs if start <= c.opened_at <= end]
        benchmark_returns.append(
            available[-1].close_price
            / (available[0].open_price * (1 + slip) * (1 + fee))
            - 1
            if available
            else D("0")
        )
    buy_hold = sum(benchmark_returns, D("0")) / len(datasets)
    return {
        "variant": variant.name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "buy_hold_return_pct": float(buy_hold * 100),
        "cash_benchmark_return_pct": 0.0,
        "return_pct": float((equity() / initial - 1) * 100),
        "drawdown_pct": float(dd * 100),
        "closed_positions": len(pnls),
        "wins": sum(p > 0 for p in pnls),
        "profit_factor": float(profit / loss) if loss else None,
        "closed_net_pnl": float(sum(pnls, D("0"))),
        "buys": buy_count,
        "open_positions": len(positions),
        "fees": float(fees),
        "mean_exposure_pct": (
            float(exposure_sum / len(timeline) * 100) if timeline else 0
        ),
        "rejected": dict(rejected),
        "closed_pnl_by_symbol": dict(pnl_by_symbol),
        "cost_multiplier": str(cost_multiplier),
        "assumed_spread_bps": str(spread_bps),
    }
