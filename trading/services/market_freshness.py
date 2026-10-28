from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from trading.models import MarketCandle, MarketHealthState
from trading.services.candles import resolution_seconds


@dataclass(frozen=True, slots=True)
class MarketFreshnessResult:
    symbol: str
    trading_enabled: bool
    reason: str
    last_candle_at: datetime | None


class MarketFreshnessService:
    def __init__(self, stale_after_hours: int) -> None:
        if stale_after_hours < 1:
            raise ValueError("stale_after_hours must be positive")
        self.stale_after = timedelta(hours=stale_after_hours)

    @transaction.atomic
    def refresh(
        self,
        symbol: str,
        resolution: str = "60",
        *,
        checked_at: datetime | None = None,
    ) -> MarketFreshnessResult:
        now = checked_at or timezone.now()
        latest = (
            MarketCandle.objects.filter(symbol=symbol, resolution=resolution)
            .order_by("-opened_at")
            .values_list("opened_at", flat=True)
            .first()
        )
        candle_closed_at = (
            latest + timedelta(seconds=resolution_seconds(resolution))
            if latest is not None
            else None
        )
        enabled = (
            candle_closed_at is not None and now - candle_closed_at <= self.stale_after
        )
        reason = (
            ""
            if enabled
            else (
                "no closed market candle is available"
                if candle_closed_at is None
                else f"market data is stale since {candle_closed_at.isoformat()}"
            )
        )
        state, _created = MarketHealthState.objects.select_for_update().get_or_create(
            symbol=symbol
        )
        was_enabled = state.trading_enabled
        state.trading_enabled = enabled
        state.reason = reason
        state.last_candle_at = latest
        if not enabled and (was_enabled or state.disabled_at is None):
            state.disabled_at = now
        elif enabled:
            state.disabled_at = None
        state.save(
            update_fields=(
                "trading_enabled",
                "reason",
                "last_candle_at",
                "disabled_at",
                "updated_at",
            )
        )
        return MarketFreshnessResult(symbol, enabled, reason, latest)

    @staticmethod
    def trading_status(symbol: str) -> MarketFreshnessResult | None:
        state = MarketHealthState.objects.filter(symbol=symbol).first()
        if state is None:
            return None
        return MarketFreshnessResult(
            state.symbol, state.trading_enabled, state.reason, state.last_candle_at
        )
