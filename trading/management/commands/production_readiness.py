from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection
from django.db.utils import DatabaseError
from django.utils import timezone

from trading.models import WorkerHeartbeat


class Command(BaseCommand):
    help = "Evaluate machine-readable production acceptance criteria."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--allow-sqlite", action="store_true")
        parser.add_argument("--allow-http", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        checks: list[tuple[str, bool, str]] = []
        checks.append(("debug_disabled", not settings.DEBUG, f"DEBUG={settings.DEBUG}"))
        checks.append(
            (
                "secret_key",
                settings.SECRET_KEY
                not in ("", "unsafe-development-key", "change-me-in-production")
                and len(settings.SECRET_KEY) >= 40,
                "configured and >=40 chars",
            )
        )
        checks.append(
            (
                "paper_only",
                settings.TRADING_MODE == "paper",
                f"TRADING_MODE={settings.TRADING_MODE}",
            )
        )
        checks.append(
            (
                "database",
                options["allow_sqlite"] or connection.vendor != "sqlite",
                f"vendor={connection.vendor}",
            )
        )
        https_ready = bool(
            settings.SECURE_SSL_REDIRECT
            and settings.SESSION_COOKIE_SECURE
            and settings.CSRF_COOKIE_SECURE
        )
        checks.append(
            (
                "https",
                options["allow_http"] or https_ready,
                f"secure_redirect/cookies={https_ready}",
            )
        )
        try:
            workers = list(WorkerHeartbeat.objects.all())
        except DatabaseError:
            workers = []
        threshold = timezone.now() - timedelta(minutes=12)
        workers_healthy = bool(workers) and all(
            item.status
            in (WorkerHeartbeat.Status.HEALTHY, WorkerHeartbeat.Status.RUNNING)
            and item.last_success_at
            and item.last_success_at >= threshold
            for item in workers
        )
        checks.append(
            (
                "workers",
                workers_healthy,
                f"healthy_recent={workers_healthy}, count={len(workers)}",
            )
        )
        backups = sorted(Path("/app/backups").glob("crypto-bot-*.sqlite3"))
        backup_recent = bool(
            backups
            and backups[-1].stat().st_mtime
            >= (timezone.now() - timedelta(hours=26)).timestamp()
        )
        checks.append(
            (
                "backup",
                backup_recent,
                f"recent_backup={backup_recent}, count={len(backups)}",
            )
        )
        failed = []
        for name, passed, detail in checks:
            self.stdout.write(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
            if not passed:
                failed.append(name)
        if failed:
            raise CommandError(f"production readiness failed: {', '.join(failed)}")
        self.stdout.write(
            self.style.SUCCESS("All production acceptance checks passed.")
        )
