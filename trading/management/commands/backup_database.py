from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection


class Command(BaseCommand):
    help = (
        "Create a transactionally consistent SQLite backup using the SQLite backup API."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--output-dir", default="/app/backups", type=str)

    def handle(self, *args: object, **options: object) -> None:
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("backup_database currently supports SQLite only")
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = output_dir / f"crypto-bot-{stamp}.sqlite3"
        connection.ensure_connection()
        source_connection = connection.connection
        if source_connection is None:
            raise CommandError("database connection is unavailable")
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)
            integrity = destination_connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
        if not integrity or integrity[0] != "ok":
            destination.unlink(missing_ok=True)
            raise CommandError("backup integrity check failed")
        destination.chmod(0o600)
        self.stdout.write(self.style.SUCCESS(str(destination)))
