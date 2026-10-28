import csv
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from .services.reset import reset_paper_data

from .forms import BotConfigurationForm
from .models import (
    Alert,
    BacktestRun,
    BotConfiguration,
    MLTrainingRun,
    MarketSnapshot,
    PaperPortfolio,
    PerformanceReport,
    StrategyOptimizationRun,
    Trade,
    TradingSignal,
    WorkerHeartbeat,
)
from .services.paper_trading import PaperBotResult, PaperTradingService
from .services.activity import activity_date


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"status": "ok", "service": "crypto-bot", "trading_mode": settings.TRADING_MODE}
    )


def ready(request: HttpRequest) -> JsonResponse:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database_ok = True
    except Exception:
        database_ok = False
    workers = list(WorkerHeartbeat.objects.all()) if database_ok else []
    threshold = timezone.now() - timedelta(minutes=12)
    workers_ok = bool(workers) and all(
        worker.status
        in (WorkerHeartbeat.Status.HEALTHY, WorkerHeartbeat.Status.RUNNING)
        and worker.last_success_at is not None
        and worker.last_success_at >= threshold
        for worker in workers
    )
    ready_now = database_ok and workers_ok and settings.TRADING_MODE == "paper"
    return JsonResponse(
        {
            "status": "ready" if ready_now else "not_ready",
            "database": database_ok,
            "workers": workers_ok,
            "paper_only": settings.TRADING_MODE == "paper",
        },
        status=200 if ready_now else 503,
    )


def get_configuration() -> BotConfiguration:
    defaults: dict[str, object] = {
        "symbols": list(settings.PAPER_BOT_SYMBOLS),
        "initial_balance": Decimal(settings.PAPER_INITIAL_BALANCE),
        "initial_tmn_balance": Decimal(settings.PAPER_INITIAL_TMN_BALANCE),
    }
    configuration, _created = BotConfiguration.objects.get_or_create(
        name="default", defaults=defaults
    )
    return configuration


def build_market_chart_data(
    symbols: list[str], start_at: datetime | None = None, end_at: datetime | None = None
) -> list[dict[str, object]]:
    charts: list[dict[str, object]] = []
    for symbol in symbols:
        snapshot_query = MarketSnapshot.objects.filter(symbol=symbol)
        trade_query = Trade.objects.filter(strategy__symbol=symbol, is_paper=True)
        if start_at:
            snapshot_query = snapshot_query.filter(captured_at__gte=start_at)
            trade_query = trade_query.filter(executed_at__gte=start_at)
        if end_at:
            snapshot_query = snapshot_query.filter(captured_at__lte=end_at)
            trade_query = trade_query.filter(executed_at__lte=end_at)
        snapshots: list[MarketSnapshot] = list(
            snapshot_query.order_by("captured_at")[:500]
        )
        trades: list[Trade] = list(
            trade_query.select_related("strategy").order_by("executed_at")[:500]
        )
        latest_signal: TradingSignal | None = (
            TradingSignal.objects.filter(strategy__symbol=symbol)
            .order_by("-created_at")
            .first()
        )
        price_points: list[dict[str, float | int]] = [
            {"x": int(item.captured_at.timestamp() * 1000), "y": float(item.last_price)}
            for item in snapshots
        ]
        buy_points: list[dict[str, float | int]] = [
            {"x": int(item.executed_at.timestamp() * 1000), "y": float(item.price)}
            for item in trades
            if item.side == Trade.Side.BUY and item.executed_at is not None
        ]
        sell_points: list[dict[str, float | int]] = [
            {"x": int(item.executed_at.timestamp() * 1000), "y": float(item.price)}
            for item in trades
            if item.side == Trade.Side.SELL and item.executed_at is not None
        ]
        charts.append(
            {
                "symbol": symbol,
                "canvas_id": f"chart-{symbol.lower()}",
                "price_points": price_points,
                "buy_points": buy_points,
                "sell_points": sell_points,
                "snapshot_count": len(snapshots),
                "trade_count": len(trades),
                "last_price": str(snapshots[-1].last_price) if snapshots else None,
                "latest_action": latest_signal.action if latest_signal else "hold",
                "latest_reason": (
                    latest_signal.reason
                    if latest_signal
                    else "No signals recorded yet."
                ),
            }
        )
    return charts


@staff_member_required
def dashboard(request: HttpRequest) -> HttpResponse:
    configuration: BotConfiguration = get_configuration()
    selected_symbol: str = request.GET.get("symbol", "").upper()
    selected_side: str = request.GET.get("side", "")
    start_at: datetime | None = _date_boundary(request.GET.get("from", ""), False)
    end_at: datetime | None = _date_boundary(request.GET.get("to", ""), True)
    visible_symbols: list[str] = (
        [selected_symbol]
        if selected_symbol in configuration.symbols
        else list(configuration.symbols)
    )
    portfolio: PaperPortfolio | None = (
        PaperPortfolio.objects.prefetch_related("positions", "wallets")
        .filter(name="Wallex Paper Bot TMN")
        .first()
    )
    latest_equity = portfolio.snapshots.first() if portfolio else None
    latest_performance = portfolio.performance_snapshots.first() if portfolio else None
    trade_query = Trade.objects.filter(
        is_paper=True, portfolio=portfolio
    ).select_related("strategy")
    if selected_symbol:
        trade_query = trade_query.filter(strategy__symbol=selected_symbol)
    if selected_side in (Trade.Side.BUY, Trade.Side.SELL):
        trade_query = trade_query.filter(side=selected_side)
    if start_at:
        trade_query = trade_query.filter(executed_at__gte=start_at)
    if end_at:
        trade_query = trade_query.filter(executed_at__lte=end_at)
    recent_trades = trade_query.order_by("-created_at")[:100]
    signal_counts = {
        row["action"]: row["count"]
        for row in TradingSignal.objects.values("action").annotate(count=Count("id"))
    }
    traded_notional: Decimal = trade_query.filter(
        status__in=(Trade.Status.FILLED, Trade.Status.PARTIALLY_FILLED)
    ).aggregate(
        total=Sum(
            ExpressionWrapper(F("price") * F("quantity"), output_field=DecimalField())
        )
    )[
        "total"
    ] or Decimal(
        "0"
    )
    context: dict[str, object] = {
        "configuration": configuration,
        "portfolio": portfolio,
        "latest_equity": latest_equity,
        "latest_performance": latest_performance,
        "recent_trades": recent_trades,
        "signal_counts": signal_counts,
        "traded_notional": traded_notional,
        "market_charts": build_market_chart_data(visible_symbols, start_at, end_at),
        "wallets": list(portfolio.wallets.all()) if portfolio else [],
        "backtests": list(
            BacktestRun.objects.filter(status=BacktestRun.Status.COMPLETED)[:10]
        ),
        "filter": {
            "symbol": selected_symbol,
            "side": selected_side,
            "from": request.GET.get("from", ""),
            "to": request.GET.get("to", ""),
        },
        "worker": _worker_status(configuration),
        "code_release": activity_date(configuration.last_code_release_at),
        "results_review": activity_date(configuration.last_results_review_at),
        "analytics_chart": _analytics_chart(portfolio),
        "alerts": list(Alert.objects.all()[:20]),
        "unread_alert_count": Alert.objects.filter(is_read=False).count(),
        "reports": list(PerformanceReport.objects.all()[:12]),
        "optimizations": list(
            StrategyOptimizationRun.objects.filter(
                status=StrategyOptimizationRun.Status.COMPLETED
            )[:10]
        ),
        "ml_runs": list(
            MLTrainingRun.objects.filter(status=MLTrainingRun.Status.COMPLETED)[:10]
        ),
    }
    return render(request, "trading/dashboard.html", context)


def _date_boundary(value: str, end: bool) -> datetime | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return timezone.make_aware(datetime.combine(parsed, time.max if end else time.min))


def _worker_status(configuration: BotConfiguration) -> dict[str, object]:
    heartbeat: WorkerHeartbeat | None = WorkerHeartbeat.objects.filter(
        name="paper-trading-worker"
    ).first()
    interval: int = int(getattr(settings, "PAPER_BOT_INTERVAL_SECONDS", 300))
    alive: bool = bool(
        configuration.enabled
        and heartbeat
        and heartbeat.status == WorkerHeartbeat.Status.HEALTHY
        and heartbeat.last_success_at
        and heartbeat.last_success_at
        >= timezone.now() - timedelta(seconds=interval * 2 + 120)
    )
    return {
        "alive": alive,
        "heartbeat": heartbeat,
        "label": "Online" if alive else "Stopped/Stale",
    }


def _analytics_chart(
    portfolio: PaperPortfolio | None,
) -> dict[str, list[dict[str, float | int]]]:
    if portfolio is None:
        return {"equity": [], "drawdown": []}
    performance = list(portfolio.performance_snapshots.order_by("captured_at")[:500])
    return {
        "equity": [
            {
                "x": int(item.captured_at.timestamp() * 1000),
                "y": float(item.total_equity),
            }
            for item in performance
        ],
        "drawdown": [
            {
                "x": int(item.captured_at.timestamp() * 1000),
                "y": float(item.maximum_drawdown * 100),
            }
            for item in performance
        ],
    }


@staff_member_required
def export_trades(request: HttpRequest) -> HttpResponse:
    query = (
        Trade.objects.filter(is_paper=True)
        .select_related("strategy")
        .order_by("executed_at")
    )
    symbol: str = request.GET.get("symbol", "").upper()
    side: str = request.GET.get("side", "")
    start_at: datetime | None = _date_boundary(request.GET.get("from", ""), False)
    end_at: datetime | None = _date_boundary(request.GET.get("to", ""), True)
    if symbol:
        query = query.filter(strategy__symbol=symbol)
    if side in (Trade.Side.BUY, Trade.Side.SELL):
        query = query.filter(side=side)
    if start_at:
        query = query.filter(executed_at__gte=start_at)
    if end_at:
        query = query.filter(executed_at__lte=end_at)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="paper-trades.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        (
            "time",
            "symbol",
            "side",
            "status",
            "requested_quantity",
            "filled_quantity",
            "reference_price",
            "execution_price",
            "notional",
            "fee",
            "slippage_bps",
            "liquidity_fraction",
            "reason",
        )
    )
    for trade in query.iterator():
        writer.writerow(
            (
                trade.executed_at.isoformat() if trade.executed_at else "",
                trade.strategy.symbol,
                trade.side,
                trade.status,
                trade.requested_quantity,
                trade.quantity,
                trade.reference_price,
                trade.price,
                trade.notional,
                trade.fee_amount,
                trade.slippage_bps,
                trade.liquidity_fraction,
                trade.execution_reason,
            )
        )
    return response


@staff_member_required
def mark_alerts_read(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        Alert.objects.filter(is_read=False).update(is_read=True)
    return redirect("trading:dashboard")


@staff_member_required
def export_reports(request: HttpRequest) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="performance-reports.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        (
            "period",
            "start",
            "end",
            "trades",
            "buys",
            "sells",
            "notional",
            "fees",
            "net_profit",
            "return",
            "drawdown",
            "win_rate",
            "profit_factor",
            "sharpe",
            "sortino",
        )
    )
    for report in PerformanceReport.objects.all().iterator():
        writer.writerow(
            (
                report.period,
                report.period_start.isoformat(),
                report.period_end.isoformat(),
                report.trade_count,
                report.buy_count,
                report.sell_count,
                report.traded_notional,
                report.fees_paid,
                report.net_profit,
                report.total_return,
                report.maximum_drawdown,
                report.win_rate,
                report.profit_factor or "",
                report.sharpe_ratio,
                report.sortino_ratio,
            )
        )
    return response


@staff_member_required
def settings_view(request: HttpRequest) -> HttpResponse:
    configuration: BotConfiguration = get_configuration()
    form: BotConfigurationForm = BotConfigurationForm(
        request.POST or None,
        instance=configuration,
        initial={"symbols": configuration.symbols},
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bot settings saved successfully.")
        return redirect("trading:settings")
    return render(
        request, "trading/settings.html", {"form": form, "configuration": configuration}
    )


@staff_member_required
@require_POST
def reset_bot(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only the primary administrator can reset the bot.")
    if request.POST.get(
        "confirmation", ""
    ).strip() != "RESET" or not request.user.check_password(
        request.POST.get("password", "")
    ):
        messages.error(
            request, "The confirmation phrase or password is incorrect; no data was deleted."
        )
        return redirect("trading:settings")
    try:
        reset_paper_data()
    except Exception:
        messages.error(
            request,
            "Reset failed; a bot cycle may be running or the backup may have failed. Please try again.",
        )
    else:
        messages.success(
            request,
            "Backup created and data cleared. The bot will restart with the saved initial balance on the next cycle.",
        )
    return redirect("trading:settings")


@staff_member_required
def run_bot(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("trading:dashboard")
    configuration: BotConfiguration = get_configuration()
    if not configuration.enabled:
        messages.error(request, "Enable the bot in settings first.")
        return redirect("trading:dashboard")
    if not configuration.has_wallex_api_key:
        messages.error(request, "The Wallex read-only API key is not configured.")
        return redirect("trading:settings")
    try:
        service: PaperTradingService = PaperTradingService.from_configuration(
            configuration
        )
        results: tuple[PaperBotResult, ...] = service.run(tuple(configuration.symbols))
    except Exception as exc:
        messages.error(request, f"Cycle failed: {exc}")
    else:
        messages.success(request, f"Analysis cycle completed for {len(results)} markets.")
    return redirect("trading:dashboard")
