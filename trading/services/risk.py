from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from trading.models import (
    BotConfiguration,
    PaperPortfolio,
    PaperPosition,
    RiskEvent,
    PaperWallet,
)
from trading.services.trade_policy import TradePolicy
from trading.services.valuation import portfolio_exposures


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allow_entry: bool
    force_exit: bool
    reason: str
    event_type: str | None = None


class RiskManagementService:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.configuration = configuration

    def evaluate(
        self,
        portfolio: PaperPortfolio,
        position: PaperPosition,
        price: Decimal,
        requested_action: str,
    ) -> RiskDecision:
        drawdown: Decimal = self.portfolio_drawdown(portfolio, position.quote_asset)
        if (
            not self.configuration.risk_halted
            and drawdown <= -self.configuration.maximum_drawdown_fraction
        ):
            self.configuration.risk_halted = True
            self.configuration.risk_halt_reason = (
                f"drawdown limit reached: {drawdown:.4%}"
            )
            self.configuration.risk_halted_at = timezone.now()
            self.configuration.save(
                update_fields=(
                    "risk_halted",
                    "risk_halt_reason",
                    "risk_halted_at",
                    "updated_at",
                )
            )
            self._record(
                portfolio,
                position,
                price,
                RiskDecision(
                    False,
                    False,
                    self.configuration.risk_halt_reason,
                    RiskEvent.EventType.DRAWDOWN_HALT,
                ),
            )
        if position.quantity > 0:
            exit_decision: RiskDecision | None = self._evaluate_exit(position, price)
            if exit_decision is not None:
                self._record(portfolio, position, price, exit_decision)
                return exit_decision
        if requested_action != "buy":
            return RiskDecision(True, False, "risk checks passed")
        if self.configuration.emergency_stop:
            decision = RiskDecision(
                False,
                False,
                "emergency stop is active",
                RiskEvent.EventType.EMERGENCY_STOP,
            )
            self._record(portfolio, position, price, decision)
            return decision
        if self.configuration.risk_halted:
            return RiskDecision(
                False,
                False,
                self.configuration.risk_halt_reason or "risk halt is active",
            )
        open_positions: int = portfolio.positions.filter(quantity__gt=0).count()
        if open_positions >= self.configuration.maximum_open_positions:
            decision = RiskDecision(
                False,
                False,
                "maximum open positions reached",
                RiskEvent.EventType.POSITION_LIMIT,
            )
            self._record(portfolio, position, price, decision)
            return decision
        return RiskDecision(True, False, "risk checks passed")

    def initialize_position_limits(
        self, position: PaperPosition, entry_price: Decimal
    ) -> None:
        position.highest_price = entry_price
        position.stop_loss_price = entry_price * (
            Decimal("1") - self.configuration.stop_loss_fraction
        )
        position.take_profit_price = entry_price * (
            Decimal("1") + self.configuration.take_profit_fraction
        )
        position.trailing_stop_price = entry_price * (
            Decimal("1") - self.configuration.trailing_stop_fraction
        )
        position.opened_at = timezone.now()

    def _evaluate_exit(
        self, position: PaperPosition, price: Decimal
    ) -> RiskDecision | None:
        position.highest_price = max(position.highest_price, price)
        dynamic_trailing: Decimal = position.highest_price * (
            Decimal("1") - self.configuration.trailing_stop_fraction
        )
        position.trailing_stop_price = max(
            position.trailing_stop_price or Decimal("0"), dynamic_trailing
        )
        position.save(
            update_fields=("highest_price", "trailing_stop_price", "updated_at")
        )
        reason = TradePolicy(self.configuration).exit_reason(
            price,
            position.stop_loss_price,
            position.take_profit_price,
            position.trailing_stop_price,
        )
        if reason:
            event = {
                "stop-loss triggered": RiskEvent.EventType.STOP_LOSS,
                "take-profit triggered": RiskEvent.EventType.TAKE_PROFIT,
                "trailing stop triggered": RiskEvent.EventType.TRAILING_STOP,
            }[reason]
            return RiskDecision(True, True, reason, event)
        return None

    @staticmethod
    def portfolio_drawdown(portfolio: PaperPortfolio, quote_asset: str) -> Decimal:
        peak: Decimal | None = None
        latest: Decimal | None = None
        snapshots = portfolio.snapshots.order_by("captured_at", "pk").iterator()
        for snapshot in snapshots:
            cash = Decimal(str(snapshot.wallet_balances.get(quote_asset, "0")))
            positions = Decimal(str(snapshot.position_values.get(quote_asset, "0")))
            equity = cash + positions
            peak = equity if peak is None else max(peak, equity)
            latest = equity
        wallet = PaperWallet.objects.filter(
            portfolio=portfolio, asset=quote_asset
        ).first()
        if wallet is not None:
            latest = wallet.balance + sum(
                (
                    p.value
                    for p in portfolio_exposures(
                        portfolio, quote_asset, Decimal("0"), Decimal("0")
                    )
                ),
                Decimal("0"),
            )
            peak = max(peak or Decimal("0"), wallet.initial_balance, latest)
        if peak in (None, Decimal("0")) or latest is None:
            return Decimal("0")
        return latest / peak - Decimal("1")

    @staticmethod
    def _record(
        portfolio: PaperPortfolio,
        position: PaperPosition,
        price: Decimal,
        decision: RiskDecision,
    ) -> None:
        if decision.event_type is None:
            return
        if decision.event_type == RiskEvent.EventType.POSITION_LIMIT:
            if RiskEvent.objects.filter(
                portfolio=portfolio,
                symbol=position.symbol,
                event_type=decision.event_type,
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).exists():
                return
        RiskEvent.objects.create(
            portfolio=portfolio,
            position=position,
            event_type=decision.event_type,
            symbol=position.symbol,
            price=price,
            details={"reason": decision.reason},
        )
