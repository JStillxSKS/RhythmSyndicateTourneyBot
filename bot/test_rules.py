"""Quick unit checks for Season 1 scoring rules (no Discord)."""
from __future__ import annotations

from rules import (
    best_verified_score,
    standings_rows,
    team_season_total,
    team_week_total,
)


def test_best_and_missing() -> None:
    subs = [
        {"user_id": "1", "week": 1, "score": 100, "verified": True},
        {"user_id": "1", "week": 1, "score": 250, "verified": True},
        {"user_id": "1", "week": 1, "score": 999, "verified": False},
        {"user_id": "2", "week": 1, "score": 50, "verified": True},
    ]
    assert best_verified_score(subs, 1, 1) == 250
    assert best_verified_score(subs, 3, 1) == 0


def test_captain_burden() -> None:
    assert team_week_total(100, 50, 1) == 150
    assert team_week_total(100, 50, 4) == 100 + 100  # 100 + 50*2


def test_season_and_standings() -> None:
    subs = [
        {"user_id": "10", "week": 1, "score": 1000, "verified": True},
        {"user_id": "11", "week": 1, "score": 500, "verified": True},
        {"user_id": "10", "week": 4, "score": 200, "verified": True},
        {"user_id": "11", "week": 4, "score": 100, "verified": True},
    ]
    # w1: 1500; w4 burden: 200 + 200 = 400; total 1900
    assert team_season_total(subs, "10", "11", through_week=4) == 1900

    teams = [
        {
            "id": "a",
            "name": "Alpha",
            "division": "classic",
            "captain_user_id": "10",
            "teammate_user_id": "11",
            "active": True,
        },
        {
            "id": "b",
            "name": "Beta",
            "division": "classic",
            "captain_user_id": "20",
            "teammate_user_id": "21",
            "active": True,
        },
    ]
    rows = standings_rows(teams, subs, "classic", through_week=4)
    assert rows[0]["name"] == "Alpha"
    assert rows[0]["total"] == 1900
    assert rows[1]["total"] == 0


if __name__ == "__main__":
    test_best_and_missing()
    test_captain_burden()
    test_season_and_standings()
    print("OK all rules tests passed")
