from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from trading.services.runtime_lock import paper_runtime_lock
from trading.services.trade_policy import TradePolicy, EntryBudget
from trading.services.valuation import portfolio_exposures
from trading.services.entry_research import VARIANTS, entry_allowed

from trading.models import (
    BotConfiguration,
    MarketCandle,
    MarketSnapshot,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperLedgerEntry,
    PaperPosition,
    PaperWallet,
    Strategy,
    Trade,
    TradingSignal,
)
from trading.services.analysis import TechnicalAnalysisService
from trading.services.base import MarketAPIError, Ticker
from trading.services.wallex import WallexMarketService
from trading.services.strategies import StrategyDecision, StrategyEngine, StrategySignal
from trading.services.strategy_profiles import StrategyProfile, profile_for
from trading.services.risk import RiskDecision, RiskManagementService
from trading.services.symbol_risk import SymbolRiskResult, SymbolRiskService
from trading.services.paper_execution import PaperExecution, PaperExecutionService
from trading.services.performance import PerformanceAnalysisService
from trading.services.candles import last_closed_open_time
from trading.services.market_freshness import (
    MarketFreshnessResult,
    MarketFreshnessService,
)
from trading.services.allocation import AllocationDecision, CommodityAllocationService


@dataclass(frozen=True, slots=True)
class PaperBotResult:
    symbol: str
    price: Decimal
    action: str
    reason: str
    trade_id: int | None


class PaperTradingService:
    FAST_PERIOD: int = 5
    SLOW_PERIOD: int = 20
    RSI_PERIOD: int = 14

    def __init__(
        self,
        market_service: WallexMarketService | None = None,
        analysis_service: TechnicalAnalysisService | None = None,
    ) -> None:
        self.market_service: WallexMarketService = (
            market_service or WallexMarketService()
        )
        self.analysis_service: TechnicalAnalysisService = (
            analysis_service or TechnicalAnalysisService()
        )
        self.strategy_engine: StrategyEngine = StrategyEngine(self.analysis_service)
        self.fast_period: int = self.FAST_PERIOD
        self.slow_period: int = self.SLOW_PERIOD
        self.rsi_period: int = self.RSI_PERIOD
        self.rsi_buy_ceiling: Decimal = Decimal("70")
        self.rsi_sell_floor: Decimal = Decimal("70")
        self.initial_balance: Decimal = Decimal(settings.PAPER_INITIAL_BALANCE)
        self.initial_tmn_balance: Decimal = Decimal(settings.PAPER_INITIAL_TMN_BALANCE)
        self.primary_quote_asset: str = "TMN"
        self.risk_level: str = BotConfiguration.RiskLevel.HIGH
        self.enabled_strategies: list[str] = [
            "sma_rsi",
            "momentum",
            "macd",
            "bollinger",
            "breakout",
        ]
        self.strategy_weights: dict[str, float] = {}
        self.consensus_threshold: float = 0.35
        self.configuration: BotConfiguration = BotConfiguration(name="runtime")
        self.risk_manager: RiskManagementService = RiskManagementService(
            self.configuration
        )
        self.execution_service: PaperExecutionService = PaperExecutionService(
            self.configuration
        )
        self.symbol_risk: SymbolRiskService = SymbolRiskService(self.configuration)
        self.allocation_service: CommodityAllocationService = (
            CommodityAllocationService(self.configuration)
        )

    @classmethod
    def from_configuration(cls, configuration: BotConfiguration) -> PaperTradingService:
        instance: PaperTradingService = cls(
            market_service=WallexMarketService(
                api_key=configuration.get_wallex_api_key()
            )
        )
        instance.fast_period = configuration.fast_period
        instance.slow_period = configuration.slow_period
        instance.rsi_period = configuration.rsi_period
        instance.rsi_buy_ceiling = configuration.rsi_buy_ceiling
        instance.rsi_sell_floor = configuration.rsi_sell_floor
        instance.initial_balance = configuration.initial_balance
        instance.initial_tmn_balance = configuration.initial_tmn_balance
        instance.risk_level = configuration.risk_level
        instance.enabled_strategies = list(configuration.enabled_strategies)
        instance.strategy_weights = {
            str(name): float(weight)
            for name, weight in configuration.strategy_weights.items()
        }
        instance.consensus_threshold = float(configuration.consensus_threshold)
        instance.configuration = configuration
        instance.risk_manager = RiskManagementService(configuration)
        instance.execution_service = PaperExecutionService(configuration)
        instance.symbol_risk = SymbolRiskService(configuration)
        instance.allocation_service = CommodityAllocationService(configuration)
        return instance

    def run(self, symbols: tuple[str, ...] | None = None) -> tuple[PaperBotResult, ...]:
        with paper_runtime_lock():
            if self.configuration.pk is not None:
                current = BotConfiguration.objects.get(pk=self.configuration.pk)
                return self.from_configuration(current)._run_unlocked(symbols)
            return self._run_unlocked(symbols)

    def _run_unlocked(
        self, symbols: tuple[str, ...] | None = None
    ) -> tuple[PaperBotResult, ...]:
        if settings.TRADING_MODE != "paper":
            raise RuntimeError(
                "PaperTradingService can only run when TRADING_MODE=paper"
            )
        selected_symbols: tuple[str, ...] = symbols or settings.PAPER_BOT_SYMBOLS
        items: list[PaperBotResult] = []
        for symbol in selected_symbols:
            try:
                items.append(self._process_symbol(symbol))
            except (MarketAPIError, ValueError) as exc:
                items.append(
                    PaperBotResult(
                        symbol=symbol.replace("/", "").replace("-", "").upper(),
                        price=Decimal("0"),
                        action=TradingSignal.Action.HOLD,
                        reason=f"market data unavailable: {exc}",
                        trade_id=None,
                    )
                )
        results: tuple[PaperBotResult, ...] = tuple(items)
        self._record_portfolio_snapshot()
        return results

    @transaction.atomic
    def _process_symbol(self, symbol: str) -> PaperBotResult:
        normalized_symbol: str = symbol.replace("/", "").replace("-", "").upper()
        ticker: Ticker = self.market_service.get_ticker(normalized_symbol)
        price: Decimal = ticker.last_price
        snapshot: MarketSnapshot = MarketSnapshot.objects.create(
            symbol=normalized_symbol,
            last_price=price,
            bid_price=ticker.bid_price,
            ask_price=ticker.ask_price,
            volume_24h=ticker.volume_24h,
        )
        strategy: Strategy = self._get_strategy(normalized_symbol)
        portfolio: PaperPortfolio = self._get_portfolio()
        base_asset, quote_asset = self._split_symbol(normalized_symbol)
        wallet: PaperWallet = self._get_wallet(portfolio, quote_asset)
        position, _created = PaperPosition.objects.select_for_update().get_or_create(
            portfolio=portfolio,
            symbol=normalized_symbol,
            defaults={
                "quantity": Decimal("0"),
                "average_entry_price": Decimal("0"),
                "base_asset": base_asset,
                "quote_asset": quote_asset,
            },
        )
        if position.base_asset != base_asset or position.quote_asset != quote_asset:
            position.base_asset = base_asset
            position.quote_asset = quote_asset
            position.save(update_fields=("base_asset", "quote_asset", "updated_at"))
        action, reason, confidence, components, fast_sma, slow_sma, rsi = (
            self._build_signal(normalized_symbol)
        )
        if action == TradingSignal.Action.BUY and position.quantity == 0:
            symbol_status: SymbolRiskResult = self.symbol_risk.entry_status(
                portfolio, normalized_symbol
            )
            if symbol_status.halted:
                action = TradingSignal.Action.HOLD
                reason = symbol_status.reason
            else:
                entry_reason: str | None = self._reentry_block_reason(
                    portfolio, normalized_symbol
                )
                if entry_reason is not None:
                    action = TradingSignal.Action.HOLD
                    reason = entry_reason
        freshness: MarketFreshnessResult | None = MarketFreshnessService.trading_status(
            normalized_symbol
        )
        if freshness is not None and not freshness.trading_enabled:
            action = TradingSignal.Action.HOLD
            reason = freshness.reason
        if action == TradingSignal.Action.BUY and position.quantity == 0:
            allocation: AllocationDecision = self.allocation_service.evaluate(
                portfolio, wallet, normalized_symbol
            )
            if not allocation.allowed:
                action = TradingSignal.Action.HOLD
                reason = allocation.reason
        risk_decision: RiskDecision = self.risk_manager.evaluate(
            portfolio, position, price, action
        )
        if risk_decision.force_exit:
            action = TradingSignal.Action.SELL
            reason = risk_decision.reason
        elif action == TradingSignal.Action.BUY and not risk_decision.allow_entry:
            action = TradingSignal.Action.HOLD
            reason = risk_decision.reason
        if action == TradingSignal.Action.BUY and position.quantity == 0:
            entry = self._entry_budget(portfolio, wallet, normalized_symbol, confidence)
            if entry.cash <= 0:
                action, reason = TradingSignal.Action.HOLD, entry.reason
        signal: TradingSignal = TradingSignal.objects.create(
            strategy=strategy,
            snapshot=snapshot,
            action=action,
            fast_sma=fast_sma,
            slow_sma=slow_sma,
            rsi=rsi,
            reason=reason,
            confidence=confidence,
            component_signals=components,
        )
        trade: Trade | None = self._execute_paper_signal(
            signal, portfolio, wallet, position, snapshot
        )
        return PaperBotResult(
            symbol=normalized_symbol,
            price=price,
            action=action,
            reason=reason,
            trade_id=trade.pk if trade else None,
        )

    def _reentry_block_reason(
        self, portfolio: PaperPortfolio, symbol: str
    ) -> str | None:
        cooldown: int = settings.PAPER_REENTRY_COOLDOWN_MINUTES
        if cooldown == 0:
            return None
        latest_exit: Trade | None = (
            Trade.objects.filter(
                portfolio=portfolio,
                strategy__symbol=symbol,
                side=Trade.Side.SELL,
                is_paper=True,
                status__in=(Trade.Status.FILLED, Trade.Status.PARTIALLY_FILLED),
            )
            .order_by("-executed_at", "-pk")
            .first()
        )
        if latest_exit is None or latest_exit.executed_at is None:
            return None
        if timezone.now() < latest_exit.executed_at + timedelta(minutes=cooldown):
            return "re-entry cooldown is active"
        latest_candle: MarketCandle | None = (
            MarketCandle.objects.filter(
                symbol=symbol,
                resolution="60",
                opened_at__lte=last_closed_open_time("60"),
            )
            .order_by("-opened_at")
            .first()
        )
        if (
            latest_candle is None
            or latest_candle.opened_at + timedelta(hours=1) <= latest_exit.executed_at
        ):
            return "waiting for a new closed candle after exit"
        return None

    def _build_signal(self, symbol: str) -> tuple[
        str,
        str,
        Decimal,
        list[dict[str, str | float]],
        Decimal | None,
        Decimal | None,
        Decimal | None,
    ]:
        source_candles: list[MarketCandle] = list(
            MarketCandle.objects.filter(
                symbol=symbol,
                resolution="60",
                opened_at__lte=last_closed_open_time("60"),
            ).order_by("-opened_at")[:100]
        )
        raw_prices: list[Decimal] = [c.close_price for c in source_candles]
        if not raw_prices:
            return (
                TradingSignal.Action.HOLD,
                "waiting for closed hourly candles",
                Decimal("0"),
                [],
                None,
                None,
                None,
            )
        prices: list[float] = [float(price) for price in raw_prices]
        prices.reverse()
        profile: StrategyProfile = profile_for(self.configuration, symbol)
        final, confidence, reason, decisions = self.strategy_engine.evaluate(
            prices,
            profile.enabled_strategies,
            profile.strategy_weights,
            profile.consensus_threshold,
            profile.engine_parameters,
        )
        fast: Decimal | None = None
        slow: Decimal | None = None
        rsi: Decimal | None = None
        if len(prices) >= max(profile.slow_period, profile.rsi_period + 1):
            fast = Decimal(
                str(
                    self._last_value(
                        self.analysis_service.sma(prices, profile.fast_period)
                    )
                )
            )
            slow = Decimal(
                str(
                    self._last_value(
                        self.analysis_service.sma(prices, profile.slow_period)
                    )
                )
            )
            rsi = Decimal(
                str(
                    self._last_value(
                        self.analysis_service.rsi(prices, profile.rsi_period)
                    )
                )
            )
        action_map: dict[StrategySignal, str] = {
            StrategySignal.BUY: TradingSignal.Action.BUY,
            StrategySignal.SELL: TradingSignal.Action.SELL,
            StrategySignal.HOLD: TradingSignal.Action.HOLD,
        }
        components: list[dict[str, str | float]] = [
            item.as_dict() for item in decisions
        ]
        if final is StrategySignal.BUY:
            decision_at = timezone.now().replace(minute=0, second=0, microsecond=0)
            for variant in VARIANTS[1:]:
                allowed, filter_reason = entry_allowed(
                    list(reversed(source_candles)),
                    decision_at,
                    self.configuration,
                    variant,
                )
                components.append(
                    {
                        "strategy": f"research:{variant.name}",
                        "signal": "pass" if allowed else "block",
                        "confidence": 0.0,
                        "reason": filter_reason,
                        "mode": "shadow_only",
                        "candle_boundary": decision_at.isoformat(),
                        "assumed_spread_bps": 10.0,
                    }
                )
        return (
            action_map[final],
            reason,
            Decimal(str(confidence)),
            components,
            fast,
            slow,
            rsi,
        )

    @staticmethod
    def _last_value(values: tuple[float | None, ...]) -> float:
        value: float | None = values[-1]
        if value is None:
            raise RuntimeError("indicator did not produce a value")
        return value

    @staticmethod
    def _get_strategy(symbol: str) -> Strategy:
        strategy, _created = Strategy.objects.get_or_create(
            name=f"Composite Paper {symbol}",
            defaults={
                "symbol": symbol,
                "timeframe": "1h",
                "status": Strategy.Status.ACTIVE,
                "parameters": {"engine": "weighted-consensus"},
            },
        )
        return strategy

    def _get_portfolio(self) -> PaperPortfolio:
        initial: Decimal = self.initial_tmn_balance
        portfolio, _created = PaperPortfolio.objects.select_for_update().get_or_create(
            name="Wallex Paper Bot TMN",
            defaults={
                "quote_asset": self.primary_quote_asset,
                "initial_balance": initial,
                "cash_balance": initial,
            },
        )
        return portfolio

    @staticmethod
    def _split_symbol(symbol: str) -> tuple[str, str]:
        for quote_asset in ("USDT", "TMN"):
            if symbol.endswith(quote_asset) and len(symbol) > len(quote_asset):
                return symbol[: -len(quote_asset)], quote_asset
        raise ValueError(f"unsupported quote asset in symbol: {symbol}")

    def _get_wallet(self, portfolio: PaperPortfolio, asset: str) -> PaperWallet:
        initial_balance: Decimal = (
            self.initial_balance if asset == "USDT" else self.initial_tmn_balance
        )
        wallet, created = PaperWallet.objects.select_for_update().get_or_create(
            portfolio=portfolio,
            asset=asset,
            defaults={"initial_balance": initial_balance, "balance": initial_balance},
        )
        if created:
            PaperLedgerEntry.objects.create(
                wallet=wallet,
                entry_type=PaperLedgerEntry.EntryType.INITIAL,
                amount=initial_balance,
                balance_after=initial_balance,
                description=f"Initial {asset} paper funding",
            )
        return wallet

    @transaction.atomic
    def _record_portfolio_snapshot(self) -> PaperPortfolioSnapshot:
        portfolio: PaperPortfolio = self._get_portfolio()
        wallet_balances: dict[str, str] = {
            wallet.asset: str(wallet.balance) for wallet in portfolio.wallets.all()
        }
        position_values: dict[str, Decimal] = {}
        positions: list[PaperPosition] = list(
            portfolio.positions.filter(quantity__gt=0)
        )
        for position in positions:
            latest: Decimal | None = (
                MarketSnapshot.objects.filter(symbol=position.symbol)
                .order_by("-captured_at")
                .values_list("last_price", flat=True)
                .first()
            )
            if latest is not None:
                position_values[position.quote_asset] = (
                    position_values.get(position.quote_asset, Decimal("0"))
                    + position.quantity * latest
                )
        primary_wallet: PaperWallet | None = portfolio.wallets.filter(
            asset=self.primary_quote_asset
        ).first()
        primary_cash: Decimal = (
            primary_wallet.balance if primary_wallet else Decimal("0")
        )
        primary_positions: Decimal = position_values.get(
            self.primary_quote_asset, Decimal("0")
        )
        primary_realized: Decimal = (
            primary_wallet.realized_pnl if primary_wallet else Decimal("0")
        )
        snapshot: PaperPortfolioSnapshot = PaperPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            cash_balance=primary_cash,
            positions_value=primary_positions,
            total_equity=primary_cash + primary_positions,
            realized_pnl=primary_realized,
            wallet_balances=wallet_balances,
            position_values={
                asset: str(value) for asset, value in position_values.items()
            },
        )
        PerformanceAnalysisService().record_portfolio(portfolio)
        return snapshot

    def _execute_paper_signal(
        self,
        signal: TradingSignal,
        portfolio: PaperPortfolio,
        wallet: PaperWallet,
        position: PaperPosition,
        snapshot: MarketSnapshot,
    ) -> Trade | None:
        now = timezone.now()
        if signal.action == TradingSignal.Action.BUY and position.quantity == 0:
            entry = self._entry_budget(
                portfolio, wallet, position.symbol, signal.confidence
            )
            allocation: AllocationDecision = self.allocation_service.evaluate(
                portfolio, wallet, position.symbol
            )
            maximum_cash_cost: Decimal = min(
                wallet.balance, allocation.available_amount, entry.cash
            )
            budget: Decimal = maximum_cash_cost
            if budget <= 0:
                return None
            reference: Decimal = snapshot.ask_price or snapshot.last_price
            requested_quantity: Decimal = budget / reference
            execution: PaperExecution | None = self.execution_service.execute(
                position.symbol,
                Trade.Side.BUY,
                requested_quantity,
                snapshot.bid_price or snapshot.last_price,
                reference,
            )
            if execution is None:
                return None
            cash_cost: Decimal = -execution.net_cash_change
            if cash_cost > maximum_cash_cost:
                execution = self.execution_service.execute(
                    position.symbol,
                    Trade.Side.BUY,
                    requested_quantity * maximum_cash_cost / cash_cost,
                    snapshot.bid_price or snapshot.last_price,
                    reference,
                )
            if execution is None:
                return None
            if -execution.net_cash_change > maximum_cash_cost + Decimal("0.000001"):
                return None
            if (
                position.quote_asset == "TMN"
                and execution.gross_notional < self.configuration.minimum_order_tmn
            ):
                return None
            wallet.balance += execution.net_cash_change
            wallet.realized_pnl -= execution.fee_amount
            position.quantity = execution.filled_quantity
            position.average_entry_price = execution.execution_price
            self.risk_manager.initialize_position_limits(
                position, execution.execution_price
            )
            wallet.save(update_fields=("balance", "realized_pnl", "updated_at"))
            position.save(
                update_fields=(
                    "quantity",
                    "average_entry_price",
                    "highest_price",
                    "stop_loss_price",
                    "take_profit_price",
                    "trailing_stop_price",
                    "opened_at",
                    "updated_at",
                )
            )
            trade: Trade = Trade.objects.create(
                strategy=signal.strategy,
                portfolio=portfolio,
                side=Trade.Side.BUY,
                quantity=execution.filled_quantity,
                price=execution.execution_price,
                quote_asset=wallet.asset,
                notional=execution.gross_notional,
                status=self._execution_status(execution),
                is_paper=True,
                executed_at=now,
                execution_reason=signal.reason,
                requested_quantity=execution.requested_quantity,
                reference_price=execution.reference_price,
                fee_amount=execution.fee_amount,
                slippage_amount=execution.slippage_amount,
                slippage_bps=execution.slippage_bps,
                simulated_latency_ms=execution.simulated_latency_ms,
                liquidity_fraction=execution.liquidity_fraction,
            )
            PaperLedgerEntry.objects.create(
                wallet=wallet,
                trade=trade,
                entry_type=PaperLedgerEntry.EntryType.BUY,
                amount=execution.net_cash_change,
                balance_after=wallet.balance,
                description=f"Paper buy {position.symbol}",
            )
            return trade
        if signal.action == TradingSignal.Action.SELL and position.quantity > 0:
            execution = self.execution_service.execute(
                position.symbol,
                Trade.Side.SELL,
                position.quantity,
                snapshot.bid_price or snapshot.last_price,
                snapshot.ask_price or snapshot.last_price,
            )
            if execution is None:
                return None
            cost: Decimal = execution.filled_quantity * position.average_entry_price
            wallet.balance += execution.net_cash_change
            realized_pnl: Decimal = execution.net_cash_change - cost
            wallet.realized_pnl += realized_pnl
            position.quantity -= execution.filled_quantity
            if position.quantity <= 0:
                position.quantity = Decimal("0")
                position.average_entry_price = Decimal("0")
                position.highest_price = Decimal("0")
                position.stop_loss_price = None
                position.take_profit_price = None
                position.trailing_stop_price = None
                position.opened_at = None
            wallet.save(update_fields=("balance", "realized_pnl", "updated_at"))
            position.save(
                update_fields=(
                    "quantity",
                    "average_entry_price",
                    "highest_price",
                    "stop_loss_price",
                    "take_profit_price",
                    "trailing_stop_price",
                    "opened_at",
                    "updated_at",
                )
            )
            trade = Trade.objects.create(
                strategy=signal.strategy,
                portfolio=portfolio,
                side=Trade.Side.SELL,
                quantity=execution.filled_quantity,
                price=execution.execution_price,
                quote_asset=wallet.asset,
                notional=execution.gross_notional,
                status=self._execution_status(execution),
                is_paper=True,
                executed_at=now,
                execution_reason=signal.reason,
                requested_quantity=execution.requested_quantity,
                reference_price=execution.reference_price,
                fee_amount=execution.fee_amount,
                slippage_amount=execution.slippage_amount,
                slippage_bps=execution.slippage_bps,
                simulated_latency_ms=execution.simulated_latency_ms,
                liquidity_fraction=execution.liquidity_fraction,
            )
            PaperLedgerEntry.objects.create(
                wallet=wallet,
                trade=trade,
                entry_type=PaperLedgerEntry.EntryType.SELL,
                amount=execution.net_cash_change,
                balance_after=wallet.balance,
                description=f"Paper sell {position.symbol}",
            )
            if position.quantity == 0:
                net_position_pnl = Decimal("0")
                for item in Trade.objects.filter(
                    portfolio=portfolio, strategy=signal.strategy
                ).order_by("-executed_at", "-pk"):
                    if item.side == Trade.Side.BUY:
                        net_position_pnl -= item.notional + item.fee_amount
                        break
                    net_position_pnl += item.notional - item.fee_amount
                self.symbol_risk.record_execution(
                    portfolio, position.symbol, net_position_pnl
                )
            return trade
        return None

    @staticmethod
    def _execution_status(execution: PaperExecution) -> str:
        return (
            Trade.Status.FILLED
            if execution.filled_quantity >= execution.requested_quantity
            else Trade.Status.PARTIALLY_FILLED
        )

    def _entry_budget(
        self,
        portfolio: PaperPortfolio,
        wallet: PaperWallet,
        symbol: str,
        confidence: Decimal,
    ) -> EntryBudget:
        exposures = portfolio_exposures(
            portfolio,
            wallet.asset,
            self.configuration.paper_fee_fraction,
            self.configuration.paper_slippage_bps / Decimal("10000"),
        )
        equity = wallet.balance + sum((p.value for p in exposures), Decimal("0"))
        return TradePolicy(self.configuration).budget(
            symbol, wallet.balance, equity, confidence, exposures
        )
