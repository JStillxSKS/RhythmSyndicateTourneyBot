"""Pure scoring rules for Season 1 (unit-testable, no Discord deps)."""
from __future__ import annotations

from typing import Any

from config import CAPTAIN_BURDEN_WEEK, SEASON_WEEKS


def best_verified_score(submissions: list[dict[str, Any]], user_id: int | str, week: int) -> int:
    """Highest verified score for a player in a week; 0 if none."""
    uid = str(user_id)
    best = 0
    for s in submissions:
        if str(s.get("user_id")) != uid:
            continue
        if int(s.get("week") or 0) != int(week):
            continue
        if not s.get("verified"):
            continue
        score = int(s.get("score") or 0)
        if score > best:
            best = score
    return best


def player_week_score(submissions: list[dict[str, Any]], user_id: int | str | None, week: int) -> int:
    """Missing player or no verified score → 0."""
    if user_id is None:
        return 0
    return best_verified_score(submissions, user_id, week)


def team_week_total(
    captain_score: int,
    teammate_score: int,
    week: int,
    *,
    captain_burden_week: int = CAPTAIN_BURDEN_WEEK,
) -> int:
    """
    Weeks 1–3: Captain + Teammate (missing already 0).
    Week 4 Captain's Burden: Captain + (Teammate × 2).
    """
    cap = max(0, int(captain_score))
    mate = max(0, int(teammate_score))
    if int(week) == int(captain_burden_week):
        return cap + (mate * 2)
    return cap + mate


def team_season_total(
    submissions: list[dict[str, Any]],
    captain_user_id: int | str | None,
    teammate_user_id: int | str | None,
    *,
    through_week: int | None = None,
    max_weeks: int = SEASON_WEEKS,
) -> int:
    """Sum of team week totals for weeks 1..through_week (inclusive)."""
    end = int(through_week) if through_week is not None else max_weeks
    end = max(1, min(end, max_weeks))
    total = 0
    for week in range(1, end + 1):
        cap = player_week_score(submissions, captain_user_id, week)
        mate = player_week_score(submissions, teammate_user_id, week)
        total += team_week_total(cap, mate, week)
    return total


def team_week_breakdown(
    submissions: list[dict[str, Any]],
    captain_user_id: int | str | None,
    teammate_user_id: int | str | None,
    week: int,
) -> dict[str, int | bool]:
    cap = player_week_score(submissions, captain_user_id, week)
    mate = player_week_score(submissions, teammate_user_id, week)
    total = team_week_total(cap, mate, week)
    return {
        "captain_score": cap,
        "teammate_score": mate,
        "team_total": total,
        "captain_burden": int(week) == CAPTAIN_BURDEN_WEEK,
    }


def standings_rows(
    teams: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
    division: str,
    *,
    through_week: int | None = None,
) -> list[dict[str, Any]]:
    """Teams in a division ranked by cumulative season total (desc)."""
    div = (division or "").lower().strip()
    rows: list[dict[str, Any]] = []
    for t in teams:
        if not t.get("active", True):
            continue
        if (t.get("division") or "").lower() != div:
            continue
        season = team_season_total(
            submissions,
            t.get("captain_user_id"),
            t.get("teammate_user_id"),
            through_week=through_week,
        )
        rows.append(
            {
                "team_id": t.get("id"),
                "name": t.get("name") or "Unnamed",
                "division": div,
                "total": season,
                "captain_user_id": t.get("captain_user_id"),
                "teammate_user_id": t.get("teammate_user_id"),
            }
        )
    rows.sort(key=lambda r: (-int(r["total"]), str(r["name"]).lower()))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows
