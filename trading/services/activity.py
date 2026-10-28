from datetime import datetime

from django.utils import timezone


def activity_date(value: datetime | None) -> dict[str, str]:
    if value is None:
        return {"date": "Not recorded", "relative": "", "iso": ""}
    local_value: datetime = timezone.localtime(value)
    days: int = (timezone.localdate() - local_value.date()).days
    relative: str = "Today (0 days ago)" if days == 0 else f"{days} days ago"
    if days < 0:
        relative = "Future date"
    return {
        "date": local_value.strftime("%Y/%m/%d"),
        "relative": relative,
        "iso": value.isoformat(),
    }
