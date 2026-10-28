import base64
import hashlib
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def default_enabled_strategies() -> list[str]:
    return ["sma_rsi", "momentum", "macd", "bollinger", "breakout"]


def default_commodity_strategy_weights() -> dict[str, float]:
    return {
        "sma_rsi": 1.0,
        "momentum": 1.0,
        "macd": 1.0,
        "bollinger": 1.0,
        "breakout": 1.0,
    }


class Strategy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"

    name = models.CharField(max_length=120, unique=True)
    symbol = models.CharField(max_length=30, default="BTC/USDT")
    timeframe = models.CharField(max_length=10, default="1h")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    parameters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "strategies"

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class BotConfiguration(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low risk"
        MEDIUM = "medium", "Balanced"
        HIGH = "high", "High risk"

    name = models.CharField(max_length=100, unique=True, default="default")
    last_code_release_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="Latest code release"
    )
    last_results_review_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="Latest results review"
    )
    enabled = models.BooleanField(default=False)
    symbols = models.JSONField(default=list)
    initial_balance = models.DecimalField(max_digits=30, decimal_places=12, default=100)
    initial_tmn_balance = models.DecimalField(
        max_digits=30, decimal_places=2, default=0
    )
    risk_level = models.CharField(
        max_length=10, choices=RiskLevel.choices, default=RiskLevel.HIGH
    )
    fast_period = models.PositiveSmallIntegerField(default=5)
    slow_period = models.PositiveSmallIntegerField(default=20)
    rsi_period = models.PositiveSmallIntegerField(default=14)
    rsi_buy_ceiling = models.DecimalField(max_digits=6, decimal_places=3, default=70)
    rsi_sell_floor = models.DecimalField(max_digits=6, decimal_places=3, default=70)
    enabled_strategies = models.JSONField(default=default_enabled_strategies)
    strategy_weights = models.JSONField(default=dict)
    consensus_threshold = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.35"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    commodity_fast_period = models.PositiveSmallIntegerField(default=5)
    commodity_slow_period = models.PositiveSmallIntegerField(default=20)
    commodity_rsi_period = models.PositiveSmallIntegerField(default=14)
    commodity_rsi_buy_ceiling = models.DecimalField(
        max_digits=6, decimal_places=3, default=70
    )
    commodity_rsi_sell_floor = models.DecimalField(
        max_digits=6, decimal_places=3, default=70
    )
    commodity_enabled_strategies = models.JSONField(default=default_enabled_strategies)
    commodity_strategy_weights = models.JSONField(
        default=default_commodity_strategy_weights
    )
    commodity_consensus_threshold = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.50"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    commodity_optimization_report = models.JSONField(default=dict, blank=True)
    commodity_allocation_cap_fraction = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.20"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    stop_loss_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.03"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    take_profit_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.06"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("10"))],
    )
    trailing_stop_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.025"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    maximum_drawdown_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.15"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    maximum_open_positions = models.PositiveSmallIntegerField(default=4)
    risk_per_trade_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.005"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("0.05")),
        ],
    )
    maximum_total_risk_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.02"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("0.20")),
        ],
    )
    maximum_symbol_allocation_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.25"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    maximum_crypto_allocation_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.60"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    minimum_order_tmn = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("50000"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    symbol_loss_streak_limit = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    symbol_loss_limit_fraction = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.05"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    symbol_halt_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    market_data_stale_hours = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(168)]
    )
    paper_fee_fraction = models.DecimalField(
        max_digits=7,
        decimal_places=6,
        default=Decimal("0.001"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("0.1"))],
    )
    paper_slippage_bps = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=Decimal("5"),
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("10000")),
        ],
    )
    paper_latency_ms = models.PositiveIntegerField(default=500)
    paper_max_book_participation = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=Decimal("0.10"),
        validators=[
            MinValueValidator(Decimal("0.00001")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    emergency_stop = models.BooleanField(default=False)
    risk_halted = models.BooleanField(default=False)
    risk_halt_reason = models.CharField(max_length=255, blank=True, default="")
    risk_halted_at = models.DateTimeField(null=True, blank=True)
    wallex_api_key_encrypted = models.BinaryField(blank=True, default=bytes)
    updated_at = models.DateTimeField(auto_now=True)

    def set_wallex_api_key(self, api_key: str) -> None:
        value: str = api_key.strip()
        if value:
            self.wallex_api_key_encrypted = self._fernet().encrypt(
                value.encode("utf-8")
            )

    def get_wallex_api_key(self) -> str:
        if not self.wallex_api_key_encrypted:
            return settings.WALLEX_API_KEY
        try:
            return (
                self._fernet()
                .decrypt(bytes(self.wallex_api_key_encrypted))
                .decode("utf-8")
            )
        except InvalidToken as exc:
            raise ValueError("The stored Wallex API key cannot be decrypted") from exc

    @property
    def has_wallex_api_key(self) -> bool:
        return bool(self.wallex_api_key_encrypted or settings.WALLEX_API_KEY)

    @staticmethod
    def _fernet() -> Fernet:
        digest: bytes = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def clean(self) -> None:
        super().clean()
        if self.fast_period >= self.slow_period:
            raise ValidationError(
                {"fast_period": "Fast period must be less than slow period."}
            )
        if self.commodity_fast_period >= self.commodity_slow_period:
            raise ValidationError(
                {
                    "commodity_fast_period": "Commodity fast period must be less than slow period."
                }
            )
        allowed_symbols: set[str] = {
            "BTCUSDT",
            "ETHUSDT",
            "SHIBUSDT",
            "DOGEUSDT",
            "SOLUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "TRXUSDT",
            "USDTTMN",
            "BNBUSDT",
            "BTCTMN",
            "ETHTMN",
            "SHIBTMN",
            "DOGETMN",
            "SOLTMN",
            "XRPTMN",
            "ADATMN",
            "TRXTMN",
            "BNBTMN",
            "USOONTMN",
            "UNGONTMN",
            "PPLTONTMN",
            "XAUTTMN",
            "SLVONTMN",
            "COPXONTMN",
        }
        normalized: list[str] = [str(symbol).upper() for symbol in self.symbols]
        invalid: set[str] = set(normalized) - allowed_symbols
        if invalid:
            raise ValidationError(
                {"symbols": f"Unsupported symbols: {', '.join(sorted(invalid))}"}
            )
        if not normalized:
            raise ValidationError({"symbols": "Select at least one symbol."})
        self.symbols = normalized

    def __str__(self) -> str:
        return self.name


class Trade(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FILLED = "filled", "Filled"
        PARTIALLY_FILLED = "partial", "Partially filled"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"

    strategy = models.ForeignKey(
        Strategy, on_delete=models.PROTECT, related_name="trades"
    )
    portfolio = models.ForeignKey(
        "PaperPortfolio",
        on_delete=models.PROTECT,
        related_name="trades",
        null=True,
        blank=True,
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(
        max_digits=24, decimal_places=10, validators=[MinValueValidator(0)]
    )
    price = models.DecimalField(
        max_digits=24, decimal_places=10, validators=[MinValueValidator(0)]
    )
    quote_asset = models.CharField(max_length=15, default="USDT")
    notional = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    is_paper = models.BooleanField(default=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_reason = models.CharField(max_length=255, blank=True, default="")
    requested_quantity = models.DecimalField(
        max_digits=30, decimal_places=12, default=0
    )
    reference_price = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    fee_amount = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    slippage_amount = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    slippage_bps = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    simulated_latency_ms = models.PositiveIntegerField(default=0)
    liquidity_fraction = models.DecimalField(
        max_digits=12, decimal_places=10, default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} {self.strategy.symbol}"


class MarketSnapshot(models.Model):
    symbol = models.CharField(max_length=30, db_index=True)
    last_price = models.DecimalField(max_digits=30, decimal_places=12)
    bid_price = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    ask_price = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    volume_24h = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-captured_at",)
        indexes = [models.Index(fields=("symbol", "captured_at"))]

    def __str__(self):
        return f"{self.symbol} @ {self.last_price}"


class MarketCandle(models.Model):
    symbol = models.CharField(max_length=30, db_index=True)
    resolution = models.CharField(max_length=10)
    opened_at = models.DateTimeField(db_index=True)
    open_price = models.DecimalField(max_digits=30, decimal_places=12)
    high_price = models.DecimalField(max_digits=30, decimal_places=12)
    low_price = models.DecimalField(max_digits=30, decimal_places=12)
    close_price = models.DecimalField(max_digits=30, decimal_places=12)
    volume = models.DecimalField(max_digits=30, decimal_places=12)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-opened_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("symbol", "resolution", "opened_at"),
                name="unique_market_candle",
            )
        ]


class OrderBookSnapshot(models.Model):
    symbol = models.CharField(max_length=30, db_index=True)
    best_bid = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    best_ask = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    spread = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    spread_bps = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    bid_depth = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    ask_depth = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    bids = models.JSONField(default=list)
    asks = models.JSONField(default=list)
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-captured_at",)


class PaperPortfolio(models.Model):
    name = models.CharField(max_length=100, unique=True, default="Wallex Paper Bot")
    quote_asset = models.CharField(max_length=15, default="USDT")
    initial_balance = models.DecimalField(max_digits=30, decimal_places=12)
    cash_balance = models.DecimalField(max_digits=30, decimal_places=12)
    realized_pnl = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PaperWallet(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="wallets"
    )
    asset = models.CharField(max_length=15)
    initial_balance = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    balance = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    realized_pnl = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "asset"), name="unique_paper_wallet"
            )
        ]

    def __str__(self) -> str:
        return f"{self.portfolio.name} {self.asset}: {self.balance}"


class PaperPosition(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="positions"
    )
    symbol = models.CharField(max_length=30)
    base_asset = models.CharField(max_length=15, default="")
    quote_asset = models.CharField(max_length=15, default="USDT")
    quantity = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    average_entry_price = models.DecimalField(
        max_digits=30, decimal_places=12, default=0
    )
    highest_price = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    stop_loss_price = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    take_profit_price = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    trailing_stop_price = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "symbol"), name="unique_paper_position"
            )
        ]

    def __str__(self):
        return f"{self.symbol}: {self.quantity}"


class PaperPortfolioSnapshot(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="snapshots"
    )
    cash_balance = models.DecimalField(max_digits=30, decimal_places=12)
    positions_value = models.DecimalField(max_digits=30, decimal_places=12)
    total_equity = models.DecimalField(max_digits=30, decimal_places=12)
    realized_pnl = models.DecimalField(max_digits=30, decimal_places=12)
    wallet_balances = models.JSONField(default=dict)
    position_values = models.JSONField(default=dict)
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-captured_at",)

    def __str__(self):
        return f"{self.portfolio.name}: {self.total_equity}"


class PaperLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        INITIAL = "initial", "Initial funding"
        BUY = "buy", "Paper buy"
        SELL = "sell", "Paper sell"
        ADJUSTMENT = "adjustment", "Adjustment"

    wallet = models.ForeignKey(
        PaperWallet, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    trade = models.ForeignKey(Trade, on_delete=models.PROTECT, null=True, blank=True)
    entry_type = models.CharField(max_length=12, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=30, decimal_places=12)
    balance_after = models.DecimalField(max_digits=30, decimal_places=12)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class MarketHealthState(models.Model):
    symbol = models.CharField(max_length=30, unique=True)
    trading_enabled = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, default="")
    last_candle_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("symbol",)

    def __str__(self) -> str:
        return f"{self.symbol}: {'enabled' if self.trading_enabled else 'disabled'}"


class SymbolRiskState(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="symbol_risk_states"
    )
    symbol = models.CharField(max_length=30)
    consecutive_losses = models.PositiveSmallIntegerField(default=0)
    cycle_realized_pnl = models.DecimalField(
        max_digits=30, decimal_places=12, default=0
    )
    halted_until = models.DateTimeField(null=True, blank=True, db_index=True)
    halt_reason = models.CharField(max_length=255, blank=True, default="")
    last_trade_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "symbol"), name="unique_symbol_risk_state"
            )
        ]

    def __str__(self) -> str:
        return f"{self.symbol}: {self.consecutive_losses} losses"


class RiskEvent(models.Model):
    class EventType(models.TextChoices):
        STOP_LOSS = "stop_loss", "Stop loss"
        TAKE_PROFIT = "take_profit", "Take profit"
        TRAILING_STOP = "trailing_stop", "Trailing stop"
        DRAWDOWN_HALT = "drawdown_halt", "Drawdown halt"
        EMERGENCY_STOP = "emergency_stop", "Emergency stop"
        POSITION_LIMIT = "position_limit", "Position limit"
        SYMBOL_HALT = "symbol_halt", "Symbol halt"

    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="risk_events"
    )
    position = models.ForeignKey(
        PaperPosition, on_delete=models.SET_NULL, null=True, blank=True
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    symbol = models.CharField(max_length=30, blank=True, default="")
    price = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class TradingSignal(models.Model):
    class Action(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"
        HOLD = "hold", "Hold"

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name="signals"
    )
    snapshot = models.ForeignKey(
        MarketSnapshot, on_delete=models.PROTECT, related_name="signals"
    )
    action = models.CharField(max_length=4, choices=Action.choices)
    fast_sma = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    slow_sma = models.DecimalField(
        max_digits=30, decimal_places=12, null=True, blank=True
    )
    rsi = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    reason = models.CharField(max_length=255)
    confidence = models.DecimalField(max_digits=6, decimal_places=5, default=0)
    component_signals = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.strategy.symbol}: {self.action}"


class BacktestRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    symbol = models.CharField(max_length=30, db_index=True)
    resolution = models.CharField(max_length=10, default="60")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RUNNING
    )
    initial_balance = models.DecimalField(max_digits=30, decimal_places=12)
    final_equity = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    total_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    buy_hold_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    excess_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    maximum_drawdown = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    trade_count = models.PositiveIntegerField(default=0)
    win_rate = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    net_profit = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    gross_profit = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    gross_loss = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    profit_factor = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    sharpe_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    sortino_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    fold_count = models.PositiveIntegerField(default=0)
    parameters = models.JSONField(default=dict)
    equity_curve = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-started_at",)


class BacktestFold(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="folds")
    fold_number = models.PositiveIntegerField()
    train_start = models.DateTimeField()
    train_end = models.DateTimeField()
    test_start = models.DateTimeField()
    test_end = models.DateTimeField()
    start_equity = models.DecimalField(max_digits=30, decimal_places=12)
    end_equity = models.DecimalField(max_digits=30, decimal_places=12)
    return_fraction = models.DecimalField(max_digits=20, decimal_places=10)
    buy_hold_return = models.DecimalField(max_digits=20, decimal_places=10)
    maximum_drawdown = models.DecimalField(max_digits=20, decimal_places=10)
    trade_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("fold_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("run", "fold_number"), name="unique_backtest_fold"
            )
        ]


class PerformanceSnapshot(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, on_delete=models.CASCADE, related_name="performance_snapshots"
    )
    total_equity = models.DecimalField(max_digits=30, decimal_places=12)
    net_profit = models.DecimalField(max_digits=30, decimal_places=12)
    total_return = models.DecimalField(max_digits=20, decimal_places=10)
    gross_profit = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    gross_loss = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    win_rate = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    profit_factor = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    maximum_drawdown = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    sharpe_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    sortino_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    closed_trades = models.PositiveIntegerField(default=0)
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-captured_at",)


class WorkerHeartbeat(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        HEALTHY = "healthy", "Healthy"
        ERROR = "error", "Error"

    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.RUNNING
    )
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_finished_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    cycles = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ("name",)


class Alert(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class AlertType(models.TextChoices):
        TRADE = "trade", "Trade"
        RISK = "risk", "Risk"
        WORKER = "worker", "Worker"
        DRAWDOWN = "drawdown", "Drawdown"

    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    title = models.CharField(max_length=160)
    message = models.TextField()
    source_key = models.CharField(max_length=160, unique=True)
    metadata = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class PerformanceReport(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    period = models.CharField(max_length=10, choices=Period.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    trade_count = models.PositiveIntegerField(default=0)
    buy_count = models.PositiveIntegerField(default=0)
    sell_count = models.PositiveIntegerField(default=0)
    traded_notional = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    fees_paid = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    net_profit = models.DecimalField(max_digits=30, decimal_places=12, default=0)
    total_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    maximum_drawdown = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    win_rate = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    profit_factor = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    sharpe_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    sortino_ratio = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period_end",)
        constraints = [
            models.UniqueConstraint(
                fields=("period", "period_start"),
                name="unique_performance_report_period",
            )
        ]


class StrategyOptimizationRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    symbol = models.CharField(max_length=30, db_index=True)
    resolution = models.CharField(max_length=10, default="60")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RUNNING
    )
    candle_count = models.PositiveIntegerField(default=0)
    candidate_count = models.PositiveIntegerField(default=0)
    best_parameters = models.JSONField(default=dict)
    train_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    validation_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    test_return = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    test_drawdown = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    overfit_gap = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    stability_score = models.DecimalField(max_digits=12, decimal_places=10, default=0)
    market_regime = models.CharField(max_length=30, default="unknown")
    sensitivity = models.JSONField(default=list)
    top_candidates = models.JSONField(default=list)
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)


class MarketRegimeSnapshot(models.Model):
    class Regime(models.TextChoices):
        TREND_UP = "trend_up", "Uptrend"
        TREND_DOWN = "trend_down", "Downtrend"
        RANGING = "ranging", "Ranging"
        VOLATILE = "volatile", "Volatile"

    symbol = models.CharField(max_length=30, db_index=True)
    regime = models.CharField(max_length=20, choices=Regime.choices)
    trend_strength = models.DecimalField(max_digits=20, decimal_places=10)
    volatility = models.DecimalField(max_digits=20, decimal_places=10)
    confidence = models.DecimalField(max_digits=10, decimal_places=8)
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-detected_at",)


class MLFeatureRow(models.Model):
    symbol = models.CharField(max_length=30, db_index=True)
    opened_at = models.DateTimeField(db_index=True)
    horizon = models.PositiveSmallIntegerField(default=3)
    features = models.JSONField(default=dict)
    target_up = models.BooleanField()
    future_return = models.DecimalField(max_digits=20, decimal_places=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("opened_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("symbol", "opened_at", "horizon"), name="unique_ml_feature_row"
            )
        ]


class MLTrainingRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    symbol = models.CharField(max_length=30, db_index=True)
    model_type = models.CharField(max_length=40, default="logistic_regression")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RUNNING
    )
    horizon = models.PositiveSmallIntegerField(default=3)
    dataset_size = models.PositiveIntegerField(default=0)
    train_size = models.PositiveIntegerField(default=0)
    validation_size = models.PositiveIntegerField(default=0)
    test_size = models.PositiveIntegerField(default=0)
    feature_names = models.JSONField(default=list)
    coefficients = models.JSONField(default=dict)
    scaler = models.JSONField(default=dict)
    validation_metrics = models.JSONField(default=dict)
    test_metrics = models.JSONField(default=dict)
    feature_importance = models.JSONField(default=dict)
    drift_report = models.JSONField(default=dict)
    drift_score = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    drift_detected = models.BooleanField(default=False)
    latest_probability_up = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True
    )
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)
