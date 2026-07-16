"""Offline smoke: teams, week, scores, standings — no Discord required."""
from __future__ import annotations

import sys
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT_DIR))

from config import STATE_PATH  # noqa: E402
from rules import standings_rows, team_week_total  # noqa: E402
from scores import record_submission  # noqa: E402
from state import empty_state, new_team_id, save_state  # noqa: E402


def main() -> None:
    # Use a throwaway state file so we don't clobber real data
    import config

    smoke_path = config.PROJECT_DIR / "data" / "rs_state_smoke.json"
    config.STATE_PATH = smoke_path  # type: ignore
    # state module already imported STATE_PATH — patch both
    import state as state_mod

    state_mod.STATE_PATH = smoke_path

    st = empty_state()
    st["teams"] = [
        {
            "id": new_team_id(),
            "name": "Smoke Alpha",
            "division": "classic",
            "captain_user_id": "1001",
            "teammate_user_id": "1002",
            "active": True,
        },
        {
            "id": new_team_id(),
            "name": "Smoke Beta",
            "division": "classic",
            "captain_user_id": "2001",
            "teammate_user_id": "2002",
            "active": True,
        },
    ]
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["song_title"] = "Smoke Test Song"
    save_state(st)

    sub, msg = record_submission(st, user_id=1001, score=900_000, source="smoke", verified=True)
    assert sub and sub["verified"], msg
    sub2, msg2 = record_submission(st, user_id=1002, score=100_000, source="smoke", verified=True)
    assert sub2 and sub2["verified"], msg2
    # best replace
    sub3, _ = record_submission(st, user_id=1001, score=950_000, source="smoke", verified=True)
    assert sub3

    rows = standings_rows(st["teams"], st["submissions"], "classic", through_week=1)
    assert rows[0]["name"] == "Smoke Alpha"
    assert rows[0]["total"] == 950_000 + 100_000
    assert team_week_total(200, 50, 4) == 300

    # Week closed → pending without staff
    st["weeks"]["1"]["status"] = "closed"
    pending, pmsg = record_submission(st, user_id=2001, score=1, source="smoke")
    assert pending is not None and pending["verified"] is False, pmsg

    # Staff verified while closed
    ok, omsg = record_submission(
        st, user_id=2001, score=50_000, source="admin", verified=True, approved_by=1
    )
    assert ok and ok["verified"] is True, omsg

    print("OK smoke_state passed")
    print(f"  temp state: {smoke_path}")
    print(f"  alpha total: {rows[0]['total']:,}")


if __name__ == "__main__":
    main()
