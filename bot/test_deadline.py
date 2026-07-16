"""Offline checks for Friday deadline helper."""
from __future__ import annotations

from datetime import datetime, timezone

from deadline import default_week_close_utc
from config import RS_TZ


def test_saturday_open_lands_next_friday() -> None:
    # Saturday 2026-07-18 10:00 PT
    sat = datetime(2026, 7, 18, 17, 0, 0, tzinfo=timezone.utc)  # 10:00 PT (PDT = UTC-7)
    close = default_week_close_utc(sat)
    local = close.astimezone(RS_TZ)
    assert local.weekday() == 4, local  # Friday
    assert local.hour == 23 and local.minute == 59
    assert local.day == 24  # week of Jul 18 → Fri Jul 24


def test_after_friday_deadline_jumps() -> None:
    # Friday 23:59:30 PT already past deadline → next Friday
    fri = datetime(2026, 7, 25, 6, 59, 30, tzinfo=timezone.utc)  # ~23:59:30 PDT Jul 24
    # Use clearly after Fri Jul 24 23:59 PT
    after = datetime(2026, 7, 25, 7, 5, 0, tzinfo=timezone.utc)
    close = default_week_close_utc(after)
    local = close.astimezone(RS_TZ)
    assert local.weekday() == 4
    assert local > after.astimezone(RS_TZ)


if __name__ == "__main__":
    test_saturday_open_lands_next_friday()
    test_after_friday_deadline_jumps()
    print("OK deadline tests passed")
