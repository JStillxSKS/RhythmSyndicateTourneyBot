"""Smoke tests for verse card renderers."""
from __future__ import annotations

import sys
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from render_versus import (  # noqa: E402
    STYLE_LABELS,
    VerseMatchup,
    VerseSide,
    matchup_from_teams,
    render_verse,
    write_previews,
)


def test_all_styles_png() -> None:
    m = VerseMatchup(
        side_a=VerseSide("Pulse Core", "NeonKai", "RimshotRex", 1_892_400, "classic", 1),
        side_b=VerseSide("Steel Sticks", "GhostKick", "MetroMaya", 1_841_050, "classic", 2),
        week=2,
        window_open=True,
    )
    for style in STYLE_LABELS:
        png = render_verse(m if style != "title" else VerseMatchup(
            side_a=VerseSide("Hex Grid", "Vex", "Glyph", 2_640_000, "fusion", 1),
            side_b=VerseSide("Phase Lock", "Orbit", "Drift", 2_510_200, "fusion", 2),
            week=4,
            burden=True,
            window_open=False,
        ), style)  # type: ignore[arg-type]
        assert png[:8] == b"\x89PNG\r\n\x1a\n", style
        assert len(png) > 3000, style
        print(f"ok {style} {len(png)} bytes")


def test_matchup_from_state() -> None:
    state = {
        "season": {"name": "Season 1", "current_week": 1},
        "weeks": {"1": {"status": "open", "number": 1}},
        "teams": [],
        "submissions": [
            {"user_id": "10", "week": 1, "score": 1000, "verified": True},
            {"user_id": "11", "week": 1, "score": 500, "verified": True},
            {"user_id": "20", "week": 1, "score": 900, "verified": True},
            {"user_id": "21", "week": 1, "score": 400, "verified": True},
        ],
    }
    ta = {
        "id": "a",
        "name": "Alpha",
        "division": "classic",
        "captain_user_id": "10",
        "teammate_user_id": "11",
    }
    tb = {
        "id": "b",
        "name": "Beta",
        "division": "classic",
        "captain_user_id": "20",
        "teammate_user_id": "21",
    }
    m = matchup_from_teams(state, ta, tb, name_a=("A", "B"), name_b=("C", "D"))
    assert m.side_a.score == 1500
    assert m.side_b.score == 1300
    assert m.window_open is True


if __name__ == "__main__":
    test_all_styles_png()
    test_matchup_from_state()
    paths = write_previews()
    for p in paths:
        print(f"preview {p}")
    print("ALL VERSE TESTS OK")
