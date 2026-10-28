from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from trading.models import (
    BotConfiguration,
    PaperPortfolio,
    RiskEvent,
    SymbolRiskState,
)


@dataclass(frozen=True, slots=True)
class SymbolRiskResult:
    halted: bool
    reason: str
    halted_until: datetime | None = None


class SymbolRiskService:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.configuration = configuration

    @transaction.atomic
    def entry_status(self, portfolio: PaperPortfolio, symbol: str) -> SymbolRiskResult:
        state, _created = SymbolRiskState.objects.select_for_update().get_or_create(
            portfolio=portfolio, symbol=symbol
        )
        now = timezone.now()
        if state.halted_until is None:
            return SymbolRiskResult(False, "")
        if now < state.halted_until:
            return SymbolRiskResult(
                True,
                f"symbol halted until {state.halted_until.isoformat()}",
                state.halted_until,
            )
        state.consecutive_losses = 0
        state.cycle_realized_pnl = Decimal("0")
        state.halted_until = None
        state.halt_reason = ""
        state.save(
            update_fields=(
                "consecutive_losses",
                "cycle_realized_pnl",
                "halted_until",
                "halt_reason",
                "updated_at",
            )
        )
        return SymbolRiskResult(False, "")

    @transaction.atomic
    def record_execution(
        self,
        portfolio: PaperPortfolio,
        symbol: str,
        realized_pnl: Decimal,
    ) -> SymbolRiskState:
        state, _created = SymbolRiskState.objects.select_for_update().get_or_create(
            portfolio=portfolio, symbol=symbol
        )
        now = timezone.now()
        if state.halted_until is not None and now >= state.halted_until:
            state.consecutive_losses = 0
            state.cycle_realized_pnl = Decimal("0")
            state.halted_until = None
            state.halt_reason = ""
        state.cycle_realized_pnl += realized_pnl
        state.consecutive_losses = (
            state.consecutive_losses + 1 if realized_pnl < 0 else 0
        )
        state.last_trade_at = now

        loss_cap = (
            portfolio.initial_balance * self.configuration.symbol_loss_limit_fraction
        )
        reason = ""
        if state.consecutive_losses >= self.configuration.symbol_loss_streak_limit:
            reason = f"{state.consecutive_losses} consecutive losing executions"
        elif state.cycle_realized_pnl <= -loss_cap:
            reason = f"symbol loss cap reached: {state.cycle_realized_pnl}"
        if reason and state.halted_until is None:
            state.halted_until = now + timedelta(
                days=self.configuration.symbol_halt_days
            )
            state.halt_reason = reason
            RiskEvent.objects.create(
                portfolio=portfolio,
                event_type=RiskEvent.EventType.SYMBOL_HALT,
                symbol=symbol,
                details={
                    "reason": reason,
                    "halted_until": state.halted_until.isoformat(),
                    "consecutive_losses": state.consecutive_losses,
                    "cycle_realized_pnl": str(state.cycle_realized_pnl),
                },
            )
        state.save()
        return state
