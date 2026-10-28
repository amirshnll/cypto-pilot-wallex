from datetime import datetime, timezone

from django.test import SimpleTestCase

from trading.services.candles import last_closed_open_time, resolution_seconds


class CandleTimingTests(SimpleTestCase):
    def test_resolution_and_closed_cutoff(self) -> None:
        now = datetime(2026, 9, 2, 10, 35, tzinfo=timezone.utc)

        self.assertEqual(resolution_seconds("60"), 3600)
        self.assertEqual(
            last_closed_open_time("60", now),
            datetime(2026, 9, 2, 9, 35, tzinfo=timezone.utc),
        )
