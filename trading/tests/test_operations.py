import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TransactionTestCase


class DatabaseBackupTests(TransactionTestCase):
    def test_backup_command_creates_integrity_checked_database(self) -> None:
        with TemporaryDirectory() as directory:
            call_command("backup_database", output_dir=directory)
            backups = list(Path(directory).glob("crypto-bot-*.sqlite3"))

            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as connection:
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
