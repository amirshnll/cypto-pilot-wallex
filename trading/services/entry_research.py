from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from trading.models import BotConfiguration, MarketCandle


@dataclass(frozen=True)
class FilterVariant:
    name: str
    trend: bool = False
    cost: bool = False


VARIANTS = (
    FilterVariant("baseline"),
    FilterVariant("trend_4h", trend=True),
    FilterVariant("cost", cost=True),
    FilterVariant("trend_4h_and_cost", True, True),
)


def entry_allowed(
    candles: Sequence[MarketCandle],
    at: datetime,
    config: BotConfiguration,
    variant: FilterVariant,
    spread_bps: Decimal = Decimal("10"),
) -> tuple[bool, str]:
    history = [c for c in candles if c.opened_at + timedelta(hours=1) <= at]
    if not variant.trend and not variant.cost:
        return True, "baseline"
    if len(history) < 100:
        return False, "insufficient_history"
    history = history[-100:]
    if history[-1].opened_at + timedelta(hours=1) != at or any(
        b.opened_at - a.opened_at != timedelta(hours=1)
        for a, b in zip(history, history[1:])
    ):
        return False, "gapped_history"
    if variant.trend:
        groups: dict[datetime, list[MarketCandle]] = {}
        for candle in history:
            utc = candle.opened_at.astimezone(timezone.utc)
            bucket = utc.replace(
                hour=utc.hour // 4 * 4, minute=0, second=0, microsecond=0
            )
            groups.setdefault(bucket, []).append(candle)
        closes = [
            group[-1].close_price
            for bucket, group in sorted(groups.items())
            if len(group) == 4
            and group[0].opened_at == bucket
            and group[-1].opened_at + timedelta(hours=1) == bucket + timedelta(hours=4)
            and bucket + timedelta(hours=4) <= at
        ]
        if len(closes) < 21:
            return False, "insufficient_4h_history"
        slow = sum(closes[-20:]) / 20
        previous_slow = sum(closes[-21:-1]) / 20
        fast = sum(closes[-5:]) / 5
        if not (closes[-1] > slow and fast > slow and slow > previous_slow):
            return False, "4h_trend_not_confirmed"
    if variant.cost:
        ranges = [
            max(
                c.high_price - c.low_price,
                abs(c.high_price - p.close_price),
                abs(c.low_price - p.close_price),
            )
            for p, c in zip(history[-15:-1], history[-14:])
        ]
        atr_fraction = sum(ranges) / 14 / history[-1].close_price
        friction = (
            config.paper_fee_fraction * 2
            + config.paper_slippage_bps / Decimal("10000") * 2
            + spread_bps / Decimal("10000")
        )

        if atr_fraction < friction * 2:
            return False, "movement_too_small_for_cost"
    return True, "passed"
