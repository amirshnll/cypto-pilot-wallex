from io import StringIO
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import transaction

from trading.models import BotConfiguration, Trade, WorkerHeartbeat
from trading.services.runtime_lock import paper_runtime_lock


def reset_paper_data() -> str:
    if settings.TRADING_MODE != "paper":
        raise ValueError("Reset is only allowed in paper trading mode.")
    with paper_runtime_lock():
        if Trade.objects.filter(is_paper=False).exists():
            raise ValueError("Live trade data exists; automatic deletion is not allowed.")
        output = StringIO()
        backup_dir = (
            Path(settings.DATABASES["default"]["NAME"]).parent / "reset-backups"
        )
        call_command("backup_database", output_dir=str(backup_dir), stdout=output)
        with transaction.atomic():
            config = BotConfiguration.objects.select_for_update().get(name="default")
            for name in ("PaperLedgerEntry", "Trade", "TradingSignal"):
                apps.get_model("trading", name).objects.all().delete()
            for model in apps.get_app_config("trading").get_models():
                if model not in (BotConfiguration, WorkerHeartbeat):
                    model.objects.all().delete()
            WorkerHeartbeat.objects.all().update(cycles=0, last_error="")
            config.enabled = True
            config.risk_halted = False
            config.risk_halt_reason = ""
            config.risk_halted_at = None
            config.emergency_stop = False
            config.commodity_optimization_report = {}
            config.last_results_review_at = None
            config.save(
                update_fields=(
                    "enabled",
                    "risk_halted",
                    "risk_halt_reason",
                    "risk_halted_at",
                    "emergency_stop",
                    "commodity_optimization_report",
                    "last_results_review_at",
                    "updated_at",
                )
            )
        return output.getvalue().strip()
