import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Profile, SessionLocal, Todo
from .email_service import send_deadline_email
from .schemas import EMAIL_PATTERN
from .time_utils import as_shanghai_naive, now_shanghai_naive


SendEmail = Callable[..., None]


def _env_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, minimum)


def reminder_lead_hours() -> float:
    return _env_float("REMINDER_LEAD_HOURS", 24.0, 0.0)


def reminder_interval_seconds() -> float:
    minutes = _env_float("REMINDER_CHECK_INTERVAL_MINUTES", 5.0, 0.1)
    return min(minutes * 60, 60.0)


def reminder_overdue_grace_minutes() -> float:
    return _env_float("REMINDER_OVERDUE_GRACE_MINUTES", 30.0, 0.0)


def _valid_email(value: str) -> bool:
    return bool(re.match(EMAIL_PATTERN, value.strip()))


def check_due_reminders(
    db: Session,
    *,
    user_id: int | None = None,
    now: datetime | None = None,
    lead_hours: float | None = None,
    send_email: SendEmail | None = None,
) -> dict[str, int]:
    current = as_shanghai_naive(now) if now else now_shanghai_naive()
    lead = timedelta(hours=reminder_lead_hours() if lead_hours is None else lead_hours)
    overdue_grace = timedelta(minutes=reminder_overdue_grace_minutes())
    sender = send_email or send_deadline_email
    stats = {"checked": 0, "eligible": 0, "sent": 0, "failed": 0}

    statement = select(Todo)
    if user_id is not None:
        statement = statement.where(Todo.user_id == user_id)

    for todo in db.scalars(statement.order_by(Todo.id)):
        stats["checked"] += 1
        if todo.completed or todo.due_at is None or todo.reminder_sent_at is not None:
            continue

        due_at = as_shanghai_naive(todo.due_at)
        if due_at is None or due_at - current > lead or current - due_at > overdue_grace:
            continue

        profile = db.get(Profile, todo.user_id)
        email = (profile.email if profile else "").strip()
        if not _valid_email(email):
            continue

        stats["eligible"] += 1
        try:
            sender(to_email=email, title=todo.title, due_at=due_at, notes=todo.notes or "")
            todo.reminder_sent_at = current
            db.commit()
            stats["sent"] += 1
        except Exception as exc:
            db.rollback()
            stats["failed"] += 1
            logging.warning("Todo reminder failed for todo_id=%s: %s", todo.id, type(exc).__name__)

    return stats


async def reminder_scheduler_loop() -> None:
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(reminder_interval_seconds())
        try:
            with SessionLocal() as db:
                stats = check_due_reminders(db)
            if stats["eligible"] or stats["failed"]:
                logging.info("Todo reminder scan finished: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.warning("Todo reminder scan crashed: %s", type(exc).__name__)
