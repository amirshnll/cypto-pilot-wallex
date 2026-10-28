from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from trading.models import (
    Alert,
    PerformanceReport,
    PerformanceSnapshot,
    RiskEvent,
    Trade,
    WorkerHeartbeat,
)


class AlertsReportsService:
    def run(self) -> tuple[int, int]:
        alerts: int = self.generate_alerts()
        reports: int = int(
            self.generate_report(PerformanceReport.Period.DAILY) is not None
        )
        reports += int(
            self.generate_report(PerformanceReport.Period.WEEKLY) is not None
        )
        return alerts, reports

    def generate_alerts(self) -> int:
        created: int = 0
        for event in RiskEvent.objects.order_by("-created_at")[:100]:
            severity: str = (
                Alert.Severity.CRITICAL
                if event.event_type
                in (
                    RiskEvent.EventType.DRAWDOWN_HALT,
                    RiskEvent.EventType.EMERGENCY_STOP,
                )
                else Alert.Severity.WARNING
            )
            _alert, was_created = Alert.objects.get_or_create(
                source_key=f"risk:{event.pk}",
                defaults={
                    "alert_type": Alert.AlertType.RISK,
                    "severity": severity,
                    "title": f"Risk event {event.symbol or 'Portfolio'}",
                    "message": event.get_event_type_display(),
                    "metadata": {
                        "risk_event_id": event.pk,
                        "price": str(event.price) if event.price else None,
                    },
                },
            )
            created += int(was_created)
        for worker in WorkerHeartbeat.objects.filter(
            status=WorkerHeartbeat.Status.ERROR
        ):
            key_time = worker.last_finished_at or worker.updated_at
            _alert, was_created = Alert.objects.get_or_create(
                source_key=f"worker:{worker.name}:{int(key_time.timestamp())}",
                defaults={
                    "alert_type": Alert.AlertType.WORKER,
                    "severity": Alert.Severity.CRITICAL,
                    "title": f"Worker error: {worker.name}",
                    "message": worker.last_error or "Worker execution failed",
                    "metadata": {"worker": worker.name},
                },
            )
            created += int(was_created)
        for trade in Trade.objects.filter(is_paper=True).order_by("-created_at")[:100]:
            _alert, was_created = Alert.objects.get_or_create(
                source_key=f"trade:{trade.pk}",
                defaults={
                    "alert_type": Alert.AlertType.TRADE,
                    "severity": Alert.Severity.INFO,
                    "title": f"{trade.side.upper()} paper {trade.strategy.symbol}",
                    "message": f"{trade.quantity} @ {trade.price}",
                    "metadata": {
                        "trade_id": trade.pk,
                        "fee": str(trade.fee_amount),
                        "slippage_bps": str(trade.slippage_bps),
                    },
                },
            )
            created += int(was_created)
        return created

    def generate_report(
        self, period: str, now: datetime | None = None
    ) -> PerformanceReport | None:
        current: datetime = timezone.localtime(now or timezone.now())
        if period == PerformanceReport.Period.DAILY:
            local_start = current.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=1)
            local_end = local_start + timedelta(days=1)
        elif period == PerformanceReport.Period.WEEKLY:
            this_week = current.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=current.weekday())
            local_start = this_week - timedelta(days=7)
            local_end = this_week
        else:
            raise ValueError(f"unsupported report period: {period}")
        if PerformanceReport.objects.filter(
            period=period, period_start=local_start
        ).exists():
            return None
        trades = Trade.objects.filter(
            is_paper=True,
            portfolio__name="Wallex Paper Bot TMN",
            executed_at__gte=local_start,
            executed_at__lt=local_end,
        )
        aggregate = trades.aggregate(notional=Sum("notional"), fees=Sum("fee_amount"))
        sides = {
            row["side"]: row["count"]
            for row in trades.values("side").annotate(count=Count("id"))
        }
        performance: PerformanceSnapshot | None = PerformanceSnapshot.objects.filter(
            portfolio__name="Wallex Paper Bot TMN", captured_at__lt=local_end
        ).first()
        return PerformanceReport.objects.create(
            period=period,
            period_start=local_start,
            period_end=local_end,
            trade_count=trades.count(),
            buy_count=sides.get(Trade.Side.BUY, 0),
            sell_count=sides.get(Trade.Side.SELL, 0),
            traded_notional=aggregate["notional"] or Decimal("0"),
            fees_paid=aggregate["fees"] or Decimal("0"),
            net_profit=performance.net_profit if performance else Decimal("0"),
            total_return=performance.total_return if performance else Decimal("0"),
            maximum_drawdown=(
                performance.maximum_drawdown if performance else Decimal("0")
            ),
            win_rate=performance.win_rate if performance else Decimal("0"),
            profit_factor=performance.profit_factor if performance else None,
            sharpe_ratio=performance.sharpe_ratio if performance else Decimal("0"),
            sortino_ratio=performance.sortino_ratio if performance else Decimal("0"),
            summary={
                "symbols": list(
                    trades.values_list("strategy__symbol", flat=True).distinct()
                ),
                "timezone": str(timezone.get_current_timezone()),
            },
        )
