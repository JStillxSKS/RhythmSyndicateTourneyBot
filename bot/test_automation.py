"""Unit tests for season clock + team import (no Discord)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from scheduler import evaluate_clock, in_scoring_window  # noqa: E402
from state import empty_state  # noqa: E402
from team_import import import_teams  # noqa: E402
from timeclock import clock_now, ensure_test_origins  # noqa: E402

try:
    PT = ZoneInfo("America/Los_Angeles")
except Exception:
    from datetime import timezone, timedelta

    PT = timezone(timedelta(hours=-8))


def test_window() -> None:
    # Saturday 10:00 open
    sat = datetime(2026, 7, 18, 10, 0, tzinfo=PT)
    assert in_scoring_window(sat)
    sat_early = datetime(2026, 7, 18, 9, 59, tzinfo=PT)
    assert not in_scoring_window(sat_early)
    # Friday 23:58 still open, 23:59 close boundary
    fri = datetime(2026, 7, 24, 23, 58, tzinfo=PT)
    assert in_scoring_window(fri)
    fri_end = datetime(2026, 7, 24, 23, 59, tzinfo=PT)
    assert not in_scoring_window(fri_end)
    # Wednesday mid
    wed = datetime(2026, 7, 22, 15, 0, tzinfo=PT)
    assert in_scoring_window(wed)


def test_evaluate_open_close() -> None:
    st = empty_state()
    st["weeks"]["1"]["status"] = "scheduled"
    # Sat 10 → open
    assert evaluate_clock(st, now=datetime(2026, 7, 18, 10, 5, tzinfo=PT)) == "open"
    st["weeks"]["1"]["status"] = "open"
    assert evaluate_clock(st, now=datetime(2026, 7, 18, 10, 5, tzinfo=PT)) is None
    # Fri 23:59 → close
    assert evaluate_clock(st, now=datetime(2026, 7, 24, 23, 59, tzinfo=PT)) == "close"
    st["weeks"]["1"]["status"] = "closed"
    assert evaluate_clock(st, now=datetime(2026, 7, 24, 23, 59, tzinfo=PT)) is None


def test_import_csv() -> None:
    st = empty_state()
    csv = (
        "team_name,division,captain_id,teammate_id\n"
        "Alpha,classic,111,222\n"
        "Beta,fusion,333,444\n"
    )
    ok, err = import_teams(st, csv)
    assert len(ok) == 2
    assert not err
    assert len(st["teams"]) == 2
    # duplicate name
    ok2, err2 = import_teams(st, "team_name,division,captain_id,teammate_id\nAlpha,arcade,555,666\n")
    assert not ok2
    assert err2


def test_time_scale() -> None:
    """1 real minute → 1 virtual hour when scale=1."""
    import config

    prev = config.RS_TEST_TIME
    config.RS_TEST_TIME = True
    try:
        st = empty_state()
        real0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        ensure_test_origins(st, anchor="before_open", real_now=real0)
        # at origin: virtual Sat 09:50
        v0 = clock_now(st, real_now=real0)
        assert v0.hour == 9 and v0.minute == 50
        # +10 real minutes → +10 virtual hours → 19:50 same day
        real1 = real0 + timedelta(minutes=10)
        v1 = clock_now(st, real_now=real1)
        assert v1.hour == 19 and v1.minute == 50
        st["weeks"]["1"]["status"] = "scheduled"
        # virtual Sat 10:05 after 15 real minutes from 9:50
        real_open = real0 + timedelta(minutes=15)
        assert evaluate_clock(st, now=clock_now(st, real_now=real_open)) == "open"
    finally:
        config.RS_TEST_TIME = prev


if __name__ == "__main__":
    test_window()
    test_evaluate_open_close()
    test_import_csv()
    test_time_scale()
    print("OK automation tests")
