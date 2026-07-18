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
    assert team_week_total(100, 50, 4, division="classic") == 200
    assert team_week_total(100, 50, 4, division="arcade") == 200


def test_fusion_no_captain_role() -> None:
    from rules import applies_captain_burden, division_has_captain_role, roster_labels

    assert division_has_captain_role("fusion") is False
    assert division_has_captain_role("classic") is True
    # Both slots are captains (duo kept — A/B is only for distinction)
    assert roster_labels("fusion") == ("Captain A", "Captain B")
    assert applies_captain_burden(4, "fusion") is False
    assert applies_captain_burden(4, "classic") is True
    # Week 4: no ×2 for fusion — both captains, no teammate bonus
    assert team_week_total(100, 50, 4, division="fusion") == 150

    subs = [
        {"user_id": "30", "week": 4, "score": 200, "verified": True},
        {"user_id": "31", "week": 4, "score": 100, "verified": True},
    ]
    # classic would be 400; fusion stays 300 (both captains, no burden bonus)
    assert team_season_total(subs, "30", "31", through_week=4, division="fusion") == 300
    assert team_season_total(subs, "30", "31", through_week=4, division="classic") == 400


def test_season_and_standings() -> None:
    subs = [
        {"user_id": "10", "week": 1, "score": 1000, "verified": True},
        {"user_id": "11", "week": 1, "score": 500, "verified": True},
        {"user_id": "10", "week": 4, "score": 200, "verified": True},
        {"user_id": "11", "week": 4, "score": 100, "verified": True},
    ]
    # w1: 1500; w4 burden: 200 + 200 = 400; total 1900
    assert team_season_total(subs, "10", "11", through_week=4, division="classic") == 1900

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
    test_fusion_no_captain_role()
    test_season_and_standings()
    print("OK all rules tests passed")
