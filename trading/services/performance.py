from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from math import sqrt
from statistics import fmean, pstdev

from trading.models import PaperPortfolio, PerformanceSnapshot, Trade


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    net_profit: Decimal
    total_return: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    win_rate: Decimal
    profit_factor: Decimal | None
    maximum_drawdown: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    closed_trades: int


class PerformanceAnalysisService:
    def calculate(
        self,
        initial_equity: Decimal,
        equity_curve: list[Decimal],
        closed_pnls: list[Decimal],
        periods_per_year: int = 8760,
    ) -> PerformanceMetrics:
        final: Decimal = equity_curve[-1] if equity_curve else initial_equity
        net: Decimal = final - initial_equity
        total_return: Decimal = net / initial_equity if initial_equity else Decimal("0")
        gross_profit: Decimal = sum(
            (pnl for pnl in closed_pnls if pnl > 0), Decimal("0")
        )
        gross_loss: Decimal = abs(
            sum((pnl for pnl in closed_pnls if pnl < 0), Decimal("0"))
        )
        wins: int = sum(1 for pnl in closed_pnls if pnl > 0)
        win_rate: Decimal = (
            Decimal(wins) / Decimal(len(closed_pnls)) if closed_pnls else Decimal("0")
        )
        profit_factor: Decimal | None = (
            gross_profit / gross_loss if gross_loss else None
        )
        maximum_drawdown: Decimal = self._maximum_drawdown(equity_curve)
        returns: list[float] = self._returns(equity_curve)
        sharpe: Decimal = self._sharpe(returns, periods_per_year)
        sortino: Decimal = self._sortino(returns, periods_per_year)
        return PerformanceMetrics(
            net,
            total_return,
            gross_profit,
            gross_loss,
            win_rate,
            profit_factor,
            maximum_drawdown,
            sharpe,
            sortino,
            len(closed_pnls),
        )

    def record_portfolio(self, portfolio: PaperPortfolio) -> PerformanceSnapshot:
        snapshots = list(portfolio.snapshots.order_by("captured_at"))
        curve: list[Decimal] = [item.total_equity for item in snapshots]
        hourly: dict[object, Decimal] = {}
        for item in snapshots:
            hourly[item.captured_at.replace(minute=0, second=0, microsecond=0)] = (
                item.total_equity
            )
        initial: Decimal = portfolio.initial_balance
        metrics: PerformanceMetrics = self.calculate(
            initial, list(hourly.values()), self._closed_pnls(portfolio)
        )
        metrics = replace(
            metrics, maximum_drawdown=self._maximum_drawdown([initial] + curve)
        )
        total_equity: Decimal = curve[-1] if curve else initial
        return PerformanceSnapshot.objects.create(
            portfolio=portfolio,
            total_equity=total_equity,
            net_profit=metrics.net_profit,
            total_return=metrics.total_return,
            gross_profit=metrics.gross_profit,
            gross_loss=metrics.gross_loss,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            maximum_drawdown=metrics.maximum_drawdown,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            closed_trades=metrics.closed_trades,
        )

    @staticmethod
    def _closed_pnls(portfolio: PaperPortfolio) -> list[Decimal]:
        costs: dict[str, tuple[Decimal, Decimal]] = {}
        pnls: list[Decimal] = []
        trades = (
            portfolio.trades.filter(is_paper=True)
            .select_related("strategy")
            .order_by("executed_at", "pk")
        )
        for trade in trades:
            symbol: str = trade.strategy.symbol
            if trade.side == Trade.Side.BUY:
                old_qty, old_cost = costs.get(symbol, (Decimal("0"), Decimal("0")))
                costs[symbol] = (
                    old_qty + trade.quantity,
                    old_cost + trade.notional + trade.fee_amount,
                )
            else:
                old_qty, old_cost = costs.get(symbol, (Decimal("0"), Decimal("0")))
                if old_qty <= 0:
                    continue
                allocated_cost: Decimal = old_cost * min(
                    Decimal("1"), trade.quantity / old_qty
                )
                proceeds: Decimal = trade.notional - trade.fee_amount
                pnls.append(proceeds - allocated_cost)
                costs[symbol] = (
                    max(Decimal("0"), old_qty - trade.quantity),
                    max(Decimal("0"), old_cost - allocated_cost),
                )
        return pnls

    @staticmethod
    def _returns(curve: list[Decimal]) -> list[float]:
        return [
            float(current / previous - Decimal("1"))
            for previous, current in zip(curve, curve[1:])
            if previous
        ]

    @staticmethod
    def _maximum_drawdown(curve: list[Decimal]) -> Decimal:
        peak: Decimal = Decimal("0")
        drawdown: Decimal = Decimal("0")
        for equity in curve:
            peak = max(peak, equity)
            if peak:
                drawdown = max(drawdown, (peak - equity) / peak)
        return drawdown

    @staticmethod
    def _sharpe(returns: list[float], periods_per_year: int) -> Decimal:
        deviation: float = pstdev(returns) if len(returns) > 1 else 0.0
        return (
            Decimal(str(fmean(returns) / deviation * sqrt(periods_per_year)))
            if deviation
            else Decimal("0")
        )

    @staticmethod
    def _sortino(returns: list[float], periods_per_year: int) -> Decimal:
        downside: list[float] = [min(0.0, value) for value in returns]
        downside_deviation: float = (
            sqrt(fmean([value * value for value in downside])) if downside else 0.0
        )
        return (
            Decimal(str(fmean(returns) / downside_deviation * sqrt(periods_per_year)))
            if downside_deviation
            else Decimal("0")
        )
