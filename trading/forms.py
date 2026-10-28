from __future__ import annotations

from typing import Any

from django import forms

from .models import BotConfiguration


class BotConfigurationForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in (
            "risk_per_trade_fraction",
            "maximum_total_risk_fraction",
            "maximum_symbol_allocation_fraction",
            "maximum_crypto_allocation_fraction",
            "minimum_order_tmn",
        ):
            self.fields[name].widget.attrs["form"] = "settings-form"

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            css_class = "form-check-input" if isinstance(widget, forms.CheckboxInput) else "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css_class}".strip()


    SYMBOL_CHOICES: tuple[tuple[str, str], ...] = (
        ("BTCTMN", "Bitcoin / TMN"),
        ("ETHTMN", "Ethereum / TMN"),
        ("SHIBTMN", "Shiba Inu / TMN"),
        ("DOGETMN", "Dogecoin / TMN"),
        ("SOLTMN", "Solana / TMN"),
        ("XRPTMN", "Ripple / TMN"),
        ("ADATMN", "Cardano / TMN"),
        ("TRXTMN", "Tron / TMN"),
        ("USDTTMN", "Tether / TMN"),
        ("BNBTMN", "BNB / TMN"),
        ("USOONTMN", "Digital oil / Toman"),
        ("UNGONTMN", "Natural gas / Toman"),
        ("PPLTONTMN", "Digital platinum / Toman"),
        ("XAUTTMN", "Digital gold / Toman"),
        ("SLVONTMN", "Digital silver / Toman"),
        ("COPXONTMN", "Digital copper / Toman"),
    )
    symbols = forms.MultipleChoiceField(
        choices=SYMBOL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Active markets",
    )
    wallex_api_key = forms.CharField(
        required=False,
        label="Wallex read-only API key",
        help_text="Leave blank to keep the current key.",
        widget=forms.PasswordInput(
            render_value=False, attrs={"autocomplete": "new-password"}
        ),
    )
    STRATEGY_CHOICES = (
        ("sma_rsi", "SMA + RSI"),
        ("momentum", "Momentum / ROC"),
        ("macd", "MACD"),
        ("bollinger", "Bollinger Mean Reversion"),
        ("breakout", "20-period Breakout"),
    )
    enabled_strategies = forms.MultipleChoiceField(
        choices=STRATEGY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Active strategies",
    )
    commodity_enabled_strategies = forms.MultipleChoiceField(
        choices=STRATEGY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Active commodity strategies",
    )
    reset_risk_halt = forms.BooleanField(
        required=False,
        label="Clear automatic drawdown halt",
    )

    class Meta:
        model = BotConfiguration
        fields: tuple[str, ...] = (
            "enabled",
            "symbols",
            "initial_tmn_balance",
            "risk_level",
            "fast_period",
            "slow_period",
            "rsi_period",
            "rsi_buy_ceiling",
            "rsi_sell_floor",
            "enabled_strategies",
            "consensus_threshold",
            "commodity_fast_period",
            "commodity_slow_period",
            "commodity_rsi_period",
            "commodity_rsi_buy_ceiling",
            "commodity_rsi_sell_floor",
            "commodity_enabled_strategies",
            "commodity_strategy_weights",
            "commodity_consensus_threshold",
            "commodity_allocation_cap_fraction",
            "stop_loss_fraction",
            "take_profit_fraction",
            "trailing_stop_fraction",
            "maximum_drawdown_fraction",
            "maximum_open_positions",
            "risk_per_trade_fraction",
            "maximum_total_risk_fraction",
            "maximum_symbol_allocation_fraction",
            "maximum_crypto_allocation_fraction",
            "minimum_order_tmn",
            "symbol_loss_streak_limit",
            "symbol_loss_limit_fraction",
            "symbol_halt_days",
            "market_data_stale_hours",
            "paper_fee_fraction",
            "paper_slippage_bps",
            "paper_latency_ms",
            "paper_max_book_participation",
            "emergency_stop",
        )
        labels: dict[str, str] = {
            "enabled": "Enable bot",
            "initial_tmn_balance": "Initial balance (Toman)",
            "risk_level": "Risk level",
            "fast_period": "Fast SMA period",
            "slow_period": "Slow SMA period",
            "rsi_period": "RSI period",
            "rsi_buy_ceiling": "Buy RSI ceiling",
            "rsi_sell_floor": "Sell RSI floor",
            "consensus_threshold": "Minimum crypto consensus",
            "commodity_fast_period": "Commodity fast SMA period",
            "commodity_slow_period": "Commodity slow SMA period",
            "commodity_rsi_period": "Commodity RSI period",
            "commodity_rsi_buy_ceiling": "Commodity buy RSI ceiling",
            "commodity_rsi_sell_floor": "Commodity sell RSI floor",
            "commodity_enabled_strategies": "Active commodity strategies",
            "commodity_strategy_weights": "Commodity strategy weights (JSON)",
            "commodity_consensus_threshold": "Minimum commodity consensus",
            "commodity_allocation_cap_fraction": "Maximum total commodity allocation",
            "stop_loss_fraction": "Stop loss",
            "take_profit_fraction": "Take profit",
            "trailing_stop_fraction": "Trailing stop",
            "maximum_drawdown_fraction": "Maximum drawdown",
            "maximum_open_positions": "Maximum open positions",
            "risk_per_trade_fraction": "Base risk per trade (e.g. 0.005)",
            "maximum_total_risk_fraction": "Maximum total open risk (e.g. 0.02)",
            "maximum_symbol_allocation_fraction": "Maximum allocation per symbol",
            "maximum_crypto_allocation_fraction": "Maximum total crypto allocation",
            "minimum_order_tmn": "Minimum buy amount (Toman)",
            "symbol_loss_streak_limit": "Consecutive losses before symbol halt",
            "symbol_loss_limit_fraction": "Maximum periodic loss per symbol",
            "symbol_halt_days": "Symbol halt duration (days)",
            "market_data_stale_hours": "Maximum market data age (hours)",
            "emergency_stop": "Emergency stop for new entries",
            "paper_fee_fraction": "Paper trading fee rate",
            "paper_slippage_bps": "Base slippage (basis points)",
            "paper_latency_ms": "Simulated latency (milliseconds)",
            "paper_max_book_participation": "Maximum order book participation",
        }

    def save(self, commit: bool = True) -> BotConfiguration:
        configuration: BotConfiguration = super().save(commit=False)
        api_key: str = self.cleaned_data.get("wallex_api_key", "")
        if api_key:
            configuration.set_wallex_api_key(api_key)
        if self.cleaned_data.get("reset_risk_halt"):
            configuration.risk_halted = False
            configuration.risk_halt_reason = ""
            configuration.risk_halted_at = None
        if commit:
            configuration.save()
        return configuration
