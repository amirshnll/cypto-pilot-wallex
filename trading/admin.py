from django.contrib import admin

from .models import (
    MarketSnapshot,
    MarketHealthState,
    MarketCandle,
    OrderBookSnapshot,
    BotConfiguration,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperLedgerEntry,
    PaperPosition,
    PaperWallet,
    RiskEvent,
    SymbolRiskState,
    Strategy,
    Trade,
    TradingSignal,
    BacktestRun,
    BacktestFold,
    PerformanceSnapshot,
    WorkerHeartbeat,
    Alert,
    PerformanceReport,
    StrategyOptimizationRun,
    MarketRegimeSnapshot,
    MLFeatureRow,
    MLTrainingRun,
)


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "timeframe", "status", "updated_at")
    list_filter = ("status", "timeframe")
    search_fields = ("name", "symbol")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        "strategy",
        "side",
        "quantity",
        "price",
        "fee_amount",
        "slippage_bps",
        "status",
        "is_paper",
        "created_at",
    )
    list_filter = ("side", "status", "is_paper")
    search_fields = ("strategy__name", "strategy__symbol")


admin.site.register(MarketSnapshot)
admin.site.register(MarketHealthState)
admin.site.register(MarketCandle)
admin.site.register(OrderBookSnapshot)
admin.site.register(BotConfiguration)
admin.site.register(PaperPortfolio)
admin.site.register(PaperWallet)
admin.site.register(PaperPosition)
admin.site.register(PaperPortfolioSnapshot)
admin.site.register(PaperLedgerEntry)
admin.site.register(RiskEvent)
admin.site.register(SymbolRiskState)
admin.site.register(TradingSignal)
admin.site.register(BacktestRun)
admin.site.register(BacktestFold)
admin.site.register(PerformanceSnapshot)
admin.site.register(WorkerHeartbeat)
admin.site.register(Alert)
admin.site.register(PerformanceReport)
admin.site.register(StrategyOptimizationRun)
admin.site.register(MarketRegimeSnapshot)
admin.site.register(MLFeatureRow)
admin.site.register(MLTrainingRun)
