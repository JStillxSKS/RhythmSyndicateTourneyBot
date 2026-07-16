"""Week open/close deadline helpers (America/Los_Angeles)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import RS_TZ


def default_week_close_utc(now: datetime | None = None) -> datetime:
    """
    Next Friday 11:59 PM local (PT), matching Season 1 window.
    If 'now' is already past Friday 23:59 this week, use next Friday.
    Saturday open → Friday is +6 days (common case).
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(RS_TZ)

    # Friday = weekday 4
    days_ahead = (4 - local.weekday()) % 7
    close_local = local.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(
        days=days_ahead
    )
    # If that Friday 23:59 is not strictly after now, jump a week
    if close_local <= local:
        close_local = close_local + timedelta(days=7)
    return close_local.astimezone(timezone.utc)


def default_week_open_label(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(RS_TZ)
    return local.strftime("%a %b %d · %I:%M %p %Z")
