from datetime import datetime, timedelta, timezone


SHANGHAI_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def as_shanghai_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    cleaned = value.replace(microsecond=0)
    if cleaned.tzinfo is None:
        return cleaned
    return cleaned.astimezone(SHANGHAI_TZ).replace(tzinfo=None)


def now_shanghai_naive() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None, microsecond=0)


def format_shanghai(value: datetime) -> str:
    due_at = as_shanghai_naive(value)
    return due_at.strftime("%Y-%m-%d %H:%M") if due_at else ""
