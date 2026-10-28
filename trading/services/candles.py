from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone


def resolution_seconds(resolution: str) -> int:
    normalized = resolution.strip().upper()
    if normalized.isdigit():
        return int(normalized) * 60
    aliases: dict[str, int] = {"D": 86400, "1D": 86400, "W": 604800, "1W": 604800}
    if normalized not in aliases:
        raise ValueError(f"unsupported candle resolution: {resolution}")
    return aliases[normalized]


def last_closed_open_time(resolution: str, now: datetime | None = None) -> datetime:
    current = now or timezone.now()
    return current - timedelta(seconds=resolution_seconds(resolution))
