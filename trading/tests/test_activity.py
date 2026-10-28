from datetime import datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from trading.models import BotConfiguration
from trading.services.activity import activity_date


class ActivityTests(TestCase):
    def test_elapsed_days_use_tehran_calendar_boundary(self) -> None:
        with timezone.override("Asia/Tehran"), patch(
            "trading.services.activity.timezone.now",
            return_value=datetime(2026, 10, 16, 0, 0, tzinfo=dt_timezone.utc),
        ):
            result = activity_date(
                datetime(2026, 10, 15, 20, 0, tzinfo=dt_timezone.utc)
            )
            self.assertEqual(result["date"], "2026/10/15")
            self.assertEqual(result["relative"], "1 days ago")
            self.assertIn("0 days ago", activity_date(timezone.now())["relative"])

    def test_missing_date_is_not_fabricated(self) -> None:
        self.assertEqual(activity_date(None)["date"], "Not recorded")

    def test_release_and_review_are_independent_and_old_backfill_does_not_overwrite(
        self,
    ) -> None:
        out = StringIO()
        call_command(
            "record_activity", "review", at="2026-09-29T00:00:00+03:30", stdout=out
        )
        call_command("record_activity", "release", stdout=out)
        call_command(
            "record_activity", "review", at="2026-09-01T00:00:00+03:30", stdout=out
        )
        config = BotConfiguration.objects.get(name="default")
        self.assertIsNotNone(config.last_code_release_at)
        self.assertEqual(timezone.localtime(config.last_results_review_at).day, 29)
