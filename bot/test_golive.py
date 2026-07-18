#!/usr/bin/env python3
"""
Channel go-live readiness suite (offline — no Discord token).

Simulates a full Season 1 weekend path + embed API limits + regression bugs.
Exit 0 = safe for lab channel smoke; still needs real Discord for intent/sync.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT_DIR))

import config  # noqa: E402
from dashboard import (  # noqa: E402
    build_dashboard_embed,
    build_help_embed,
    build_rules_embed,
    build_score_embed,
    build_standings_embeds,
    build_submission_reply_embed,
    build_team_embed,
    missing_submissions,
)
from rules import best_verified_score, standings_rows, team_season_total  # noqa: E402
from scores import parse_embed, record_submission  # noqa: E402
from state import empty_state, find_team_by_user, load_state, new_team_id, save_state  # noqa: E402

failures: list[str] = []
passes = 0


def ok(label: str) -> None:
    global passes
    passes += 1
    print(f"  OK  {label}")


def fail(label: str, detail: str) -> None:
    failures.append(f"{label}: {detail}")
    print(f"  FAIL  {label}: {detail}")


def check(cond: bool, label: str, detail: str = "") -> None:
    if cond:
        ok(label)
    else:
        fail(label, detail or "assertion failed")


def patch_path(path: Path) -> None:
    config.STATE_PATH = path  # type: ignore[misc]
    import state as sm

    sm.STATE_PATH = path


def make_lab_state(*, teams_per_div: int = 15) -> dict:
    st = empty_state()
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["song_title"] = "Go-Live Anthem"
    st["weeks"]["1"]["song_artist"] = "Rhythm Syndicate"
    st["weeks"]["1"]["open_at"] = "2026-07-18T17:00:00+00:00"
    st["weeks"]["1"]["close_at"] = "2026-07-25T06:59:00+00:00"
    uid = 200_000
    for div in ("classic", "fusion", "arcade"):
        for i in range(teams_per_div):
            st["teams"].append(
                {
                    "id": new_team_id(),
                    "name": f"{div[:1].upper()}{i+1:02d}-{'X' * (20 if i == 0 else 3)}",
                    "division": div,
                    "captain_user_id": str(uid),
                    "teammate_user_id": str(uid + 1),
                    "active": True,
                }
            )
            uid += 2
    return st


def field_lens(embed) -> list[int]:
    return [len(f.value or "") for f in embed.fields]


def test_weekend_ops() -> None:
    print("\n[weekend ops path]")
    st = make_lab_state(teams_per_div=8)
    # Register path already done via make_lab
    check(len(st["teams"]) == 24, "import 24 teams (8×3)")

    # Song + open already set
    check(st["weeks"]["1"]["status"] == "open", "week 1 open")

    # Pin times after open_at so pre-event score gate does not reject lab posts
    from datetime import datetime, timezone

    after_open = datetime(2026, 7, 18, 18, 0, 0, tzinfo=timezone.utc)

    # Flood of on-time scores (channel forwards)
    for t in st["teams"]:
        cap, mate = int(t["captain_user_id"]), int(t["teammate_user_id"])
        record_submission(
            st,
            user_id=cap,
            score=900_000,
            source="embed",
            message_id=cap,
            persist=False,
            submitted_at=after_open,
            score_achieved_at=after_open,
        )
        record_submission(
            st,
            user_id=mate,
            score=400_000,
            source="embed",
            message_id=mate,
            persist=False,
            submitted_at=after_open,
            score_achieved_at=after_open,
        )

    # Double-fire same message (bot restart / re-process)
    t0 = st["teams"][0]
    cap = int(t0["captain_user_id"])
    n = len(st["submissions"])
    record_submission(
        st,
        user_id=cap,
        score=1,
        source="embed",
        message_id=cap,
        persist=False,
        submitted_at=after_open,
        score_achieved_at=after_open,
    )
    check(len(st["submissions"]) == n, "re-process same message_id does not double-count")

    # Unregistered in channel
    sub, msg = record_submission(
        st, user_id=1, score=50, source="embed", persist=False, submitted_at=after_open
    )
    check(sub is None and "not on a registered" in msg.lower(), "unregistered rejected")

    # Mode mismatch still counts (meta only) — pipeline allows
    sub2, _ = record_submission(
        st,
        user_id=cap,
        score=910_000,
        source="embed",
        message_id=cap + 9_000_000,
        meta={"gameMode": "arcade", "team_division": "classic"},
        persist=False,
        submitted_at=after_open,
        score_achieved_at=after_open,
    )
    check(sub2 is not None and best_verified_score(st["submissions"], cap, 1) == 910_000, "best-of after new message")

    # Close week → late pending
    st["weeks"]["1"]["status"] = "closed"
    late_uid = int(st["teams"][1]["captain_user_id"])
    late_post = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
    # Score was done during open window; post is late → pending (not pre-event reject)
    pend, _ = record_submission(
        st,
        user_id=late_uid,
        score=999_999,
        source="embed",
        message_id=555,
        persist=False,
        submitted_at=late_post,
        score_achieved_at=after_open,
    )
    check(pend is not None and pend["verified"] is False, "closed week → pending")

    from scores import approve_submission

    approve_submission(st, pend["id"], admin_id=99, persist=False)
    check(best_verified_score(st["submissions"], late_uid, 1) == 999_999, "staff approve late counts")

    # Week 4 burden (classic team — Fusion both captains / no burden bonus)
    st["season"]["current_week"] = 4
    st["weeks"]["4"]["status"] = "open"
    st["weeks"]["4"]["open_at"] = "2026-08-08T17:00:00+00:00"
    burden_team = next(t for t in st["teams"] if t["division"] == "classic")
    bc, bm = int(burden_team["captain_user_id"]), int(burden_team["teammate_user_id"])
    w4_ok = datetime(2026, 8, 8, 18, 0, 0, tzinfo=timezone.utc)
    record_submission(
        st,
        user_id=bc,
        score=100,
        source="pg",
        week=4,
        persist=False,
        submitted_at=w4_ok,
        score_achieved_at=w4_ok,
        message_id=900001,
    )
    record_submission(
        st,
        user_id=bm,
        score=50,
        source="pg",
        week=4,
        persist=False,
        submitted_at=w4_ok,
        score_achieved_at=w4_ok,
        message_id=900002,
    )
    tot = team_season_total(
        st["submissions"], bc, bm, through_week=4, division="classic"
    )
    # w1: 910k+400k or 900k+400k depending team — just check burden math on week 4 alone
    from rules import team_week_total

    check(team_week_total(100, 50, 4, division="classic") == 200, "burden formula week 4")
    check(team_week_total(100, 50, 4, division="fusion") == 150, "fusion week 4 no burden")
    check(tot >= 200, "season includes burden week")


def test_score_set_does_not_move_current_week() -> None:
    print("\n[regression: score set week]")
    st = make_lab_state(teams_per_div=2)
    st["season"]["current_week"] = 2
    st["weeks"]["2"]["status"] = "open"
    st["weeks"]["1"]["status"] = "closed"
    uid = int(st["teams"][0]["captain_user_id"])
    # Admin fixes week 1 score while week 2 is live
    sub, msg = record_submission(
        st,
        user_id=uid,
        score=12345,
        source="admin_manual",
        verified=True,
        approved_by=1,
        week=1,
        persist=False,
    )
    check(sub is not None and int(sub["week"]) == 1, f"sub on week 1 ({msg})")
    check(int(st["season"]["current_week"]) == 2, "current_week still 2 after week=1 score set")


def test_discord_embed_limits() -> None:
    print("\n[Discord embed field limits]")
    st = make_lab_state(teams_per_div=40)  # huge board
    st["weeks"]["1"]["status"] = "open"
    # partial scores so missing list is huge
    for t in st["teams"][:5]:
        record_submission(
            st, user_id=int(t["captain_user_id"]), score=1, source="pg", persist=False
        )

    dash = build_dashboard_embed(st)
    for i, flen in enumerate(field_lens(dash)):
        check(flen <= 1024, f"dashboard field[{i}] ≤1024", f"len={flen}")

    boards = build_standings_embeds(st)
    # Lead summary card + one embed per division (Classic / Fusion / Arcade)
    check(len(boards) == 4, "standings embeds = lead + 3 divisions", f"got {len(boards)}")
    div_titles = { (emb.title or "") for emb in boards[1:] }
    check(div_titles == {"Classic", "Fusion", "Arcade"}, "three division board titles", f"{div_titles}")
    for emb in boards:
        for i, flen in enumerate(field_lens(emb)):
            check(flen <= 1024, f"standings '{emb.title}' field[{i}] ≤1024", f"len={flen}")
        check(len(emb.title or "") <= 256, "title ≤256")
        check(len(emb.description or "") <= 4096, "desc ≤4096")

    # Player surfaces
    team = st["teams"][0]
    for emb in (
        build_team_embed(st, team),
        build_score_embed(st, team, int(team["captain_user_id"])),
        build_rules_embed(),
        build_help_embed(),
        build_submission_reply_embed(verified=True, status_text="ok", score=1, week=1),
        build_submission_reply_embed(verified=False, status_text="pending " * 40, score=1, week=1),
    ):
        for i, flen in enumerate(field_lens(emb)):
            check(flen <= 1024, f"{emb.title} field[{i}]", f"len={flen}")


def test_division_and_inactive() -> None:
    print("\n[division / inactive]")
    st = make_lab_state(teams_per_div=3)
    st["teams"].append(
        {
            "id": "bench",
            "name": "Bench",
            "division": "classic",
            "captain_user_id": "9",
            "teammate_user_id": "8",
            "active": False,
        }
    )
    classic = st["teams"][0]
    record_submission(
        st, user_id=int(classic["captain_user_id"]), score=1_000_000, source="pg", persist=False
    )
    fus = standings_rows(st["teams"], st["submissions"], "fusion", through_week=1)
    check(all(r["team_id"] != classic["id"] for r in fus), "classic not in fusion board")
    cl = standings_rows(st["teams"], st["submissions"], "classic", through_week=1)
    check(all(r["name"] != "Bench" for r in cl), "inactive hidden from standings")
    check(find_team_by_user(st, 9) is None, "inactive players not matched for intake")


def test_embed_parse_variants() -> None:
    print("\n[embed parse variants]")
    import discord

    cases = [
        ("comma score", "2,500,000", 2_500_000),
        ("plain", "123456", 123456),
    ]
    for name, raw, expect in cases:
        emb = discord.Embed(description="Artist: X")
        emb.add_field(name="Song", value="Track")
        emb.add_field(name="Score", value=raw)
        emb.add_field(name="Difficulty", value="Hard")
        emb.add_field(name="Game Mode", value="Fusion")
        emb.set_author(name="P (Meta Quest)")
        data = parse_embed(emb)
        check(data is not None and data["score"] == expect, f"parse {name}", str(data))
        check(data is not None and data.get("gameMode") == "fusion", f"mode {name}")


def test_disk_reload_mid_season() -> None:
    print("\n[disk reload mid-season]")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rs.json"
        patch_path(path)
        st = make_lab_state(teams_per_div=4)
        for t in st["teams"]:
            record_submission(
                st,
                user_id=int(t["captain_user_id"]),
                score=50_000,
                source="pg",
                persist=False,
            )
        save_state(st)
        loaded = load_state()
        a = standings_rows(st["teams"], st["submissions"], "classic", through_week=1)
        b = standings_rows(loaded["teams"], loaded["submissions"], "classic", through_week=1)
        check([r["total"] for r in a] == [r["total"] for r in b], "standings stable after bot restart")
        check(loaded.get("updated_at"), "updated_at stamped")


def test_help_shows_version() -> None:
    print("\n[prove-live version]")
    emb = build_help_embed()
    blob = (emb.description or "") + (emb.footer.text if emb.footer else "")
    check(config.BOT_VERSION in blob or config.BOT_VERSION in (emb.footer.text or ""), "BOT_VERSION on help footer")
    check(config.BOT_VERSION.startswith("2026-"), f"version string set ({config.BOT_VERSION})")


def main() -> int:
    print("=" * 60)
    print(f"RS GO-LIVE SUITE  BOT_VERSION={config.BOT_VERSION}")
    print("=" * 60)
    for fn in (
        test_weekend_ops,
        test_score_set_does_not_move_current_week,
        test_discord_embed_limits,
        test_division_and_inactive,
        test_embed_parse_variants,
        test_disk_reload_mid_season,
        test_help_shows_version,
    ):
        try:
            fn()
        except Exception:
            fail(fn.__name__, traceback.format_exc())

    print("\n" + "=" * 60)
    print(f"Passed checks: {passes}")
    print(f"Failed: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    if failures:
        print("GO-LIVE SUITE FAILED")
        return 1
    print("GO-LIVE SUITE ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
