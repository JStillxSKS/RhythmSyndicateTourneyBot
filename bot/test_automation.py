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
    # Fusion still requires both captains (no solo)
    ok_solo, err_solo = import_teams(
        st, "team_name,division,captain_a_id\nSoloFire,fusion,777\n"
    )
    assert not ok_solo and err_solo
    # Fusion duo with captain_a / captain_b aliases
    ok_f, err_f = import_teams(
        st,
        "team_name,division,captain_a_id,captain_b_id\nTwinPulse,fusion,777,888\n",
    )
    assert not err_f and len(ok_f) == 1
    twin = next(t for t in st["teams"] if t["name"] == "TwinPulse")
    assert twin["division"] == "fusion"
    assert twin["captain_user_id"] == "777"
    assert twin["teammate_user_id"] == "888"
    # Classic without teammate must fail
    ok_bad, err_bad = import_teams(
        st, "team_name,division,captain_id\nNoMate,classic,999\n"
    )
    assert not ok_bad and err_bad
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


def test_reject_before_open() -> None:
    from scores import record_submission, submission_timing

    st = empty_state()
    st["teams"] = [
        {
            "id": "t1",
            "name": "Alpha",
            "division": "classic",
            "captain_user_id": "111",
            "teammate_user_id": "222",
            "active": True,
        }
    ]
    st["weeks"]["1"]["status"] = "scheduled"
    assert submission_timing(st, week=1) == "before"
    sub, msg = record_submission(st, user_id=111, score=999, persist=False)
    assert sub is None
    assert "Rejected" in msg
    assert "before" in msg.lower()
    assert not st["submissions"]

    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["open_at"] = "2026-07-18T17:00:00+00:00"  # Sat 10 AM PDT
    # Submit 1 hour before open
    early = datetime(2026, 7, 18, 16, 0, 0, tzinfo=timezone.utc)
    assert submission_timing(st, week=1, submitted_at=early) == "before"
    sub2, msg2 = record_submission(
        st, user_id=111, score=1000, persist=False, submitted_at=early
    )
    assert sub2 is None and "Rejected" in msg2

    # Submit after open
    late_ok = datetime(2026, 7, 18, 18, 0, 0, tzinfo=timezone.utc)
    assert submission_timing(st, week=1, submitted_at=late_ok) == "open"
    sub3, msg3 = record_submission(
        st, user_id=111, score=1000, persist=False, submitted_at=late_ok, message_id=1
    )
    assert sub3 is not None and sub3["verified"] is True


def test_reject_score_done_before_open() -> None:
    """Post after open is not enough — score itself must be after open_at."""
    from scores import record_submission, score_done_before_open

    st = empty_state()
    st["teams"] = [
        {
            "id": "t1",
            "name": "Alpha",
            "division": "classic",
            "captain_user_id": "111",
            "teammate_user_id": "222",
            "active": True,
        }
    ]
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["open_at"] = "2026-07-18T17:00:00+00:00"

    # Played Friday night, posted Saturday after open
    done_early = datetime(2026, 7, 17, 22, 0, 0, tzinfo=timezone.utc)
    posted_ok = datetime(2026, 7, 18, 18, 0, 0, tzinfo=timezone.utc)
    assert score_done_before_open(st, week=1, score_achieved_at=done_early) is True
    sub, msg = record_submission(
        st,
        user_id=111,
        score=5000,
        persist=False,
        submitted_at=posted_ok,
        score_achieved_at=done_early,
        score_time_source="snapshot[0].created_at",
        message_id=42,
    )
    assert sub is None
    assert "Rejected" in msg
    assert "done before" in msg.lower()
    assert not st["submissions"]

    # Same post time, but score done after open → accepted
    done_ok = datetime(2026, 7, 18, 17, 30, 0, tzinfo=timezone.utc)
    assert score_done_before_open(st, week=1, score_achieved_at=done_ok) is False
    sub2, msg2 = record_submission(
        st,
        user_id=111,
        score=5000,
        persist=False,
        submitted_at=posted_ok,
        score_achieved_at=done_ok,
        score_time_source="embed[0].timestamp",
        message_id=43,
    )
    assert sub2 is not None and sub2["verified"] is True
    assert sub2["meta"]["score_achieved_at"].startswith("2026-07-18T17:30")

    # Late post after close, but score was pre-open → still reject (not pending)
    st["weeks"]["1"]["status"] = "closed"
    st["weeks"]["1"]["close_at"] = "2026-07-25T06:59:00+00:00"
    late_post = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
    sub3, msg3 = record_submission(
        st,
        user_id=111,
        score=6000,
        persist=False,
        submitted_at=late_post,
        score_achieved_at=done_early,
        message_id=44,
    )
    assert sub3 is None and "done before" in msg3.lower()


def test_extract_score_provenance() -> None:
    """Mock forward/snapshot + embed timestamp → earliest becomes score_achieved_at."""
    from types import SimpleNamespace
    from scores import extract_score_provenance

    early = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
    mid = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    late = datetime(2026, 7, 18, 20, 0, 0, tzinfo=timezone.utc)

    emb = SimpleNamespace(timestamp=mid)
    snap = SimpleNamespace(created_at=early, embeds=[emb])
    msg = SimpleNamespace(
        created_at=late,
        embeds=[],
        message_snapshots=[snap],
        reference=None,
    )
    prov = extract_score_provenance(msg)
    assert prov["score_achieved_at"] == early
    assert "snapshot" in prov["score_source"]
    assert prov["submitted_at"] == late

    # No snapshot: use embed timestamp on the posted message
    emb2 = SimpleNamespace(timestamp=mid)
    msg2 = SimpleNamespace(
        created_at=late,
        embeds=[emb2],
        message_snapshots=[],
        reference=None,
    )
    prov2 = extract_score_provenance(msg2)
    assert prov2["score_achieved_at"] == mid
    assert "embed" in prov2["score_source"]


if __name__ == "__main__":
    test_window()
    test_evaluate_open_close()
    test_import_csv()
    test_time_scale()
    test_reject_before_open()
    test_reject_score_done_before_open()
    test_extract_score_provenance()
    print("OK automation tests")
