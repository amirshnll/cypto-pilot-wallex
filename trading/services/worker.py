from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from trading.models import WorkerHeartbeat


class WorkerHeartbeatService:
    @staticmethod
    def started(name: str) -> WorkerHeartbeat:
        heartbeat, _created = WorkerHeartbeat.objects.get_or_create(name=name)
        heartbeat.status = WorkerHeartbeat.Status.RUNNING
        heartbeat.last_started_at = timezone.now()
        heartbeat.last_error = ""
        heartbeat.save(
            update_fields=("status", "last_started_at", "last_error", "updated_at")
        )
        return heartbeat

    @staticmethod
    def succeeded(name: str) -> None:
        now = timezone.now()
        WorkerHeartbeat.objects.filter(name=name).update(
            status=WorkerHeartbeat.Status.HEALTHY,
            last_finished_at=now,
            last_success_at=now,
            last_error="",
            cycles=F("cycles") + 1,
            updated_at=now,
        )

    @staticmethod
    def failed(name: str, error: Exception) -> None:
        now = timezone.now()
        WorkerHeartbeat.objects.filter(name=name).update(
            status=WorkerHeartbeat.Status.ERROR,
            last_finished_at=now,
            last_error=str(error)[:2000],
            cycles=F("cycles") + 1,
            updated_at=now,
        )
