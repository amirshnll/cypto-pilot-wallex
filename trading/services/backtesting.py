from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from trading.models import BacktestFold, BacktestRun, BotConfiguration, MarketCandle
from trading.services.strategies import StrategyEngine, StrategySignal
from trading.services.performance import PerformanceAnalysisService, PerformanceMetrics
from trading.services.candles import last_closed_open_time, resolution_seconds
from trading.services.strategy_profiles import StrategyProfile, profile_for
from trading.services.trade_policy import TradePolicy


@dataclass(frozen=True, slots=True)
class BacktestResult:
    run_id: int
    symbol: str
    final_equity: Decimal
    total_return: Decimal
    buy_hold_return: Decimal
    excess_return: Decimal
    maximum_drawdown: Decimal
    trade_count: int
    win_rate: Decimal
    fold_count: int


class BacktestingService:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.configuration: BotConfiguration = configuration
        self.engine: StrategyEngine = StrategyEngine()
        self.fee: Decimal = configuration.paper_fee_fraction
        self.slippage: Decimal = configuration.paper_slippage_bps / Decimal("10000")

    def run(
        self,
        symbol: str,
        resolution: str = "60",
        train_size: int = 100,
        test_size: int = 50,
    ) -> BacktestResult:
        candles: list[MarketCandle] = list(
            MarketCandle.objects.filter(
                symbol=symbol,
                resolution=resolution,
                opened_at__lte=last_closed_open_time(resolution),
            ).order_by("opened_at")
        )
        minimum: int = train_size + test_size
        if len(candles) < minimum:
            raise ValueError(
                f"{symbol} needs at least {minimum} candles; found {len(candles)}"
            )
        initial: Decimal = (
            self.configuration.initial_tmn_balance
            if symbol.endswith("TMN")
            else self.configuration.initial_balance
        )
        profile: StrategyProfile = profile_for(self.configuration, symbol)
        run: BacktestRun = BacktestRun.objects.create(
            symbol=symbol,
            resolution=resolution,
            initial_balance=initial,
            parameters={
                "train_size": train_size,
                "test_size": test_size,
                "asset_class": profile.asset_class,
                "enabled_strategies": list(profile.enabled_strategies),
                "strategy_weights": profile.strategy_weights,
                "consensus_threshold": str(profile.consensus_threshold),
                "strategy_parameters": profile.engine_parameters,
                "fee_fraction": str(self.fee),
                "slippage_bps": str(self.configuration.paper_slippage_bps),
                "execution": "next_candle_open",
                "risk_policy": "shared-v2",
                "simulation_scope": "single market; no cross-market liquidity or correlation replay",
                "risk_per_trade_fraction": str(
                    self.configuration.risk_per_trade_fraction
                ),
                "maximum_total_risk_fraction": str(
                    self.configuration.maximum_total_risk_fraction
                ),
                "minimum_order_tmn": str(self.configuration.minimum_order_tmn),
            },
        )
        try:
            result: BacktestResult = self._simulate(run, candles, train_size, test_size)
        except Exception as exc:
            run.status = BacktestRun.Status.FAILED
            run.error = str(exc)
            run.completed_at = timezone.now()
            run.save(update_fields=("status", "error", "completed_at"))
            raise
        return result

    def _simulate(
        self,
        run: BacktestRun,
        candles: list[MarketCandle],
        train_size: int,
        test_size: int,
    ) -> BacktestResult:
        profile: StrategyProfile = profile_for(self.configuration, run.symbol)
        cash: Decimal = run.initial_balance
        quantity: Decimal = Decimal("0")
        entry_cost: Decimal = Decimal("0")
        wins: int = 0
        closed: int = 0
        closed_pnls: list[Decimal] = []
        trades: int = 0
        peak: Decimal = cash
        max_drawdown: Decimal = Decimal("0")
        curve: list[dict[str, str | int]] = []
        fold_number: int = 0
        first_test: int = train_size
        cursor: int = first_test
        policy = TradePolicy(self.configuration)
        entry_price = highest = Decimal("0")
        halted = False
        halted_until = None
        last_exit = None
        consecutive_losses = 0
        symbol_pnl = Decimal("0")
        while cursor < len(candles):
            fold_end: int = min(cursor + test_size, len(candles))
            fold_number += 1
            fold_start_equity: Decimal = cash + quantity * candles[cursor].open_price
            fold_peak: Decimal = fold_start_equity
            fold_dd: Decimal = Decimal("0")
            fold_trades: int = 0
            for index in range(cursor, fold_end):
                history: list[float] = [
                    float(c.close_price) for c in candles[max(0, index - 100) : index]
                ]
                signal, confidence, _reason, _parts = self.engine.evaluate(
                    history,
                    profile.enabled_strategies,
                    profile.strategy_weights,
                    profile.consensus_threshold,
                    profile.engine_parameters,
                )
                open_price: Decimal = candles[index].open_price
                current_equity = cash + quantity * open_price
                peak = max(peak, current_equity)
                halted = halted or current_equity <= peak * (
                    Decimal("1") - self.configuration.maximum_drawdown_fraction
                )
                now = candles[index].opened_at
                if halted_until is not None and now >= halted_until:
                    halted_until = None
                    consecutive_losses = 0
                    symbol_pnl = Decimal("0")
                cooldown_ok = last_exit is None or now > last_exit + timedelta(
                    minutes=settings.PAPER_REENTRY_COOLDOWN_MINUTES
                )
                if (
                    signal is StrategySignal.BUY
                    and quantity == 0
                    and cash > 0
                    and not halted
                    and halted_until is None
                    and cooldown_ok
                ):
                    fill: Decimal = open_price * (Decimal("1") + self.slippage)
                    budget = policy.budget(
                        run.symbol, cash, current_equity, Decimal(str(confidence)), []
                    ).cash
                    if budget > 0:
                        quantity = budget / (fill * (Decimal("1") + self.fee))
                        entry_cost = budget
                        cash -= budget
                        entry_price = highest = fill
                        trades += 1
                        fold_trades += 1
                exit_price = None
                if quantity > 0:
                    stop = entry_price * (
                        Decimal("1") - self.configuration.stop_loss_fraction
                    )
                    target = entry_price * (
                        Decimal("1") + self.configuration.take_profit_fraction
                    )
                    trailing = highest * (
                        Decimal("1") - self.configuration.trailing_stop_fraction
                    )
                    if (
                        policy.exit_reason(open_price, stop, target, trailing)
                        or signal is StrategySignal.SELL
                    ):
                        exit_price = open_price
                    elif policy.exit_reason(
                        candles[index].low_price, stop, None, trailing
                    ):
                        exit_price = max(stop, trailing)
                    elif policy.exit_reason(
                        candles[index].high_price, None, target, None
                    ):
                        exit_price = target
                    else:
                        highest = max(highest, candles[index].high_price)
                if exit_price is not None and quantity > 0:
                    fill = exit_price * (Decimal("1") - self.slippage)
                    proceeds: Decimal = quantity * fill * (Decimal("1") - self.fee)
                    wins += int(proceeds > entry_cost)
                    closed += 1
                    closed_pnls.append(proceeds - entry_cost)
                    pnl = proceeds - entry_cost
                    symbol_pnl += pnl
                    consecutive_losses = consecutive_losses + 1 if pnl < 0 else 0
                    if (
                        consecutive_losses
                        >= self.configuration.symbol_loss_streak_limit
                        or symbol_pnl
                        <= -run.initial_balance
                        * self.configuration.symbol_loss_limit_fraction
                    ):
                        halted_until = now + timedelta(
                            days=self.configuration.symbol_halt_days
                        )
                    last_exit = now
                    cash += proceeds
                    quantity = Decimal("0")
                    trades += 1
                    fold_trades += 1
                equity: Decimal = cash + quantity * candles[index].close_price
                peak = max(peak, equity)
                fold_peak = max(fold_peak, equity)
                max_drawdown = max(
                    max_drawdown, (peak - equity) / peak if peak else Decimal("0")
                )
                halted = (
                    halted
                    or max_drawdown >= self.configuration.maximum_drawdown_fraction
                )
                fold_dd = max(
                    fold_dd,
                    (fold_peak - equity) / fold_peak if fold_peak else Decimal("0"),
                )
                curve.append(
                    {
                        "timestamp": int(candles[index].opened_at.timestamp()),
                        "equity": str(equity),
                    }
                )
            fold_end_equity: Decimal = (
                cash + quantity * candles[fold_end - 1].close_price
            )
            fold_bh: Decimal = candles[fold_end - 1].close_price / candles[
                cursor
            ].open_price - Decimal("1")
            BacktestFold.objects.create(
                run=run,
                fold_number=fold_number,
                train_start=candles[0].opened_at,
                train_end=candles[cursor - 1].opened_at,
                test_start=candles[cursor].opened_at,
                test_end=candles[fold_end - 1].opened_at,
                start_equity=fold_start_equity,
                end_equity=fold_end_equity,
                return_fraction=fold_end_equity / fold_start_equity - Decimal("1"),
                buy_hold_return=fold_bh,
                maximum_drawdown=fold_dd,
                trade_count=fold_trades,
            )
            cursor = fold_end
        final_equity: Decimal = cash + quantity * candles[-1].close_price
        total_return: Decimal = final_equity / run.initial_balance - Decimal("1")
        buy_hold: Decimal = candles[-1].close_price / candles[
            first_test
        ].open_price - Decimal("1")
        win_rate: Decimal = Decimal(wins) / Decimal(closed) if closed else Decimal("0")
        equity_values: list[Decimal] = [
            Decimal(str(point["equity"])) for point in curve
        ]
        performance: PerformanceMetrics = PerformanceAnalysisService().calculate(
            run.initial_balance,
            equity_values,
            closed_pnls,
            periods_per_year=max(1, 31536000 // resolution_seconds(run.resolution)),
        )
        run.status = BacktestRun.Status.COMPLETED
        run.final_equity = final_equity
        run.total_return = total_return
        run.buy_hold_return = buy_hold
        run.excess_return = total_return - buy_hold
        run.maximum_drawdown = max_drawdown
        run.trade_count = trades
        run.win_rate = win_rate
        run.net_profit = performance.net_profit
        run.gross_profit = performance.gross_profit
        run.gross_loss = performance.gross_loss
        run.profit_factor = performance.profit_factor
        run.sharpe_ratio = performance.sharpe_ratio
        run.sortino_ratio = performance.sortino_ratio
        run.fold_count = fold_number
        run.equity_curve = curve
        run.completed_at = timezone.now()
        run.save()
        return BacktestResult(
            run.pk,
            run.symbol,
            final_equity,
            total_return,
            buy_hold,
            total_return - buy_hold,
            max_drawdown,
            trades,
            win_rate,
            fold_number,
        )
