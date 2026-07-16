"""Smoke tests for brand kit + banner render + embed builders (no Discord network)."""
from __future__ import annotations

import sys
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from dashboard import (  # noqa: E402
    build_announce_embed,
    build_dashboard_embed,
    build_help_embed,
    build_rules_embed,
    build_score_embed,
    build_standings_embeds,
    build_team_embed,
    build_week_status_embed,
)
from render_banners import render_hero_banner, render_hero_from_state, write_preview  # noqa: E402
from theme import EMBED_COLOR, footer_public, status_label  # noqa: E402


def sample_state() -> dict:
    return {
        "season": {"name": "Season 1", "current_week": 1},
        "weeks": {
            "1": {
                "status": "open",
                "song_title": "Paranoid",
                "song_artist": "Black Sabbath",
                "difficulty": "Extreme",
                "open_at": "2026-07-18T17:00:00+00:00",
                "close_at": "2026-07-25T06:59:00+00:00",
            }
        },
        "teams": [
            {
                "id": "t1",
                "name": "PulseCore",
                "division": "classic",
                "captain_user_id": "111",
                "teammate_user_id": "222",
                "active": True,
            },
            {
                "id": "t2",
                "name": "Steel Sticks",
                "division": "classic",
                "captain_user_id": "333",
                "teammate_user_id": "444",
                "active": True,
            },
            {
                "id": "t3",
                "name": "Arcade Rats",
                "division": "arcade",
                "captain_user_id": "555",
                "teammate_user_id": "666",
                "active": True,
            },
        ],
        "submissions": [
            {"user_id": "111", "week": 1, "score": 980000, "verified": True},
            {"user_id": "222", "week": 1, "score": 910000, "verified": True},
            {"user_id": "333", "week": 1, "score": 950000, "verified": True},
            # 444 missing
            {"user_id": "555", "week": 1, "score": 700000, "verified": True},
            {"user_id": "666", "week": 1, "score": 720000, "verified": True},
        ],
    }


def test_theme() -> None:
    assert EMBED_COLOR == 0xE10600
    assert "OPEN" in status_label("open")
    assert "/tourney" in footer_public()


def test_embeds() -> None:
    state = sample_state()
    d = build_dashboard_embed(state)
    assert d.title and "Rhythm Syndicate" in d.title
    assert d.color and d.color.value == EMBED_COLOR
    assert any(f.name == "Featured song" for f in d.fields)

    stands = build_standings_embeds(state)
    assert len(stands) == 3
    assert "Classic" in (stands[0].title or "")

    team = state["teams"][0]
    te = build_team_embed(state, team)
    assert "PulseCore" in (te.title or "")

    se = build_score_embed(state, team, 111)
    assert se.fields

    ann = build_announce_embed(state, "Season 1 is live. RS4L.", style="week_open")
    assert "OPEN" in (ann.title or "")

    wopen = build_week_status_embed(state, 1, opened=True)
    assert "opened" in (wopen.title or "").lower()

    rules = build_rules_embed()
    help_e = build_help_embed()
    assert rules.description
    assert help_e.description


def test_hero_png() -> None:
    png = render_hero_banner(
        week=1,
        season="Season 1",
        status="open",
        song="Paranoid — Black Sabbath",
        deadline="Closes Fri 11:59 PM PST",
        burden=False,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 5000

    state = sample_state()
    png2 = render_hero_from_state(state, mode="week")
    assert png2[:8] == b"\x89PNG\r\n\x1a\n"

    # Week 4 burden
    burden = render_hero_banner(week=4, status="open", burden=True)
    assert burden[:8] == b"\x89PNG\r\n\x1a\n"

    out = write_preview(
        week=1,
        status="open",
        song="Paranoid — Black Sabbath",
        deadline="Closes Fri 11:59 PM PST",
    )
    assert out.is_file()
    print(f"preview written: {out}")


def test_closed_and_burden_previews() -> None:
    from config import ASSETS_DIR

    mock = ASSETS_DIR / "mockups"
    mock.mkdir(parents=True, exist_ok=True)
    (mock / "live-hero-closed.png").write_bytes(
        render_hero_banner(week=2, status="closed", song="Riot")
    )
    (mock / "live-hero-burden.png").write_bytes(
        render_hero_banner(week=4, status="open", burden=True, song="Finale Chart")
    )
    print("wrote closed + burden previews")


if __name__ == "__main__":
    test_theme()
    test_embeds()
    test_hero_png()
    test_closed_and_burden_previews()
    # existing rules tests
    import test_rules

    test_rules.test_best_and_missing()
    test_rules.test_captain_burden()
    test_rules.test_season_and_standings()
    print("ALL VISUAL + RULES TESTS OK")
