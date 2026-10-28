from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from trading.models import BotConfiguration


class Command(BaseCommand):
    help = "Record a successful code release or a completed human results review."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("kind", choices=("release", "review"))
        parser.add_argument(
            "--at", help="Optional timezone-aware ISO timestamp for backfill."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        recorded_at = timezone.now()
        if options.get("at"):
            try:
                recorded_at = parse_datetime(options["at"])
            except ValueError as exc:
                raise CommandError("Invalid ISO timestamp") from exc
            if recorded_at is None or timezone.is_naive(recorded_at):
                raise CommandError("--at requires a timezone-aware ISO timestamp")
            if recorded_at > timezone.now():
                raise CommandError("An activity cannot be recorded in the future")
        field: str = (
            "last_code_release_at"
            if options["kind"] == "release"
            else "last_results_review_at"
        )
        configuration, _ = BotConfiguration.objects.get_or_create(name="default")
        
        from django.db.models import Q

        updated: int = (
            BotConfiguration.objects.filter(pk=configuration.pk)
            .filter(
                Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__lt": recorded_at})
            )
            .update(**{field: recorded_at})
        )
        self.stdout.write(f"{field}: {recorded_at.isoformat()} (updated={updated})")
