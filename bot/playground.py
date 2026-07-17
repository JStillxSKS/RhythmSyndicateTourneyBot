#!/usr/bin/env python3
"""
Offline tournament playground + stress harness (no Discord token required).

Simulates Season 1 chaos:
  - multi-division teams
  - score floods (best-of wins)
  - re-forward / same message_id dedupe
  - week close → pending → staff approve
  - Captain's Burden week 4
  - unregistered / zero / inactive edge cases
  - division isolation
  - standings stability under load
  - disk save/load round-trip
  - concurrent writers (thread flood)

Usage (from project root or bot/):
  python bot/playground.py
  python bot/playground.py --flood 5000
  python bot/playground.py --teams 40 --flood 2000

Includes season-clock automation scenarios (open/close evaluate + test time scale).
"""
from __future__ import annotations

import argparse
import random
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import config  # noqa: E402
from lifecycle import advance_to_next_week, close_week, open_week  # noqa: E402
from rules import standings_rows, team_season_total, team_week_total  # noqa: E402
from scheduler import evaluate_clock, in_scoring_window  # noqa: E402
from scores import (  # noqa: E402
    approve_submission,
    find_submission_by_message_id,
    parse_embed,
    record_submission,
)
from state import (  # noqa: E402
    empty_state,
    find_team_by_user,
    load_state,
    new_team_id,
    save_state,
)
from timeclock import clock_now, ensure_test_origins  # noqa: E402

try:
    from zoneinfo import ZoneInfo

    _PT = ZoneInfo("America/Los_Angeles")
except Exception:
    _PT = timezone(timedelta(hours=-8), name="PST")


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

class _Fail(Exception):
    pass


def _ok(label: str) -> None:
    print(f"  OK  {label}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise _Fail(msg)


def _patch_state_path(path: Path) -> None:
    config.STATE_PATH = path  # type: ignore[misc]
    import state as state_mod

    state_mod.STATE_PATH = path


def _make_season(
    *,
    teams_per_div: int = 8,
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    st = empty_state()
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["song_title"] = "Playground Anthem"
    st["weeks"]["1"]["song_artist"] = "Rhythm Syndicate"
    teams: list[dict[str, Any]] = []
    uid = 10_000
    for div in ("classic", "fusion", "arcade"):
        for i in range(teams_per_div):
            cap = uid
            mate = uid + 1
            uid += 2
            teams.append(
                {
                    "id": new_team_id(),
                    "name": f"{div[:3].upper()}-{i + 1:02d}-{rng.randint(100, 999)}",
                    "division": div,
                    "captain_user_id": str(cap),
                    "teammate_user_id": str(mate),
                    "active": True,
                }
            )
    # One inactive team that must never appear in standings
    teams.append(
        {
            "id": new_team_id(),
            "name": "Bench Warmers",
            "division": "classic",
            "captain_user_id": "1",
            "teammate_user_id": "2",
            "active": False,
        }
    )
    st["teams"] = teams
    return st


def _all_player_ids(st: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for t in st["teams"]:
        if not t.get("active", True):
            continue
        for k in ("captain_user_id", "teammate_user_id"):
            try:
                ids.append(int(t[k]))
            except (TypeError, ValueError, KeyError):
                pass
    return ids


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_basic_open_week(st: dict[str, Any]) -> None:
    players = _all_player_ids(st)
    _assert(len(players) >= 4, "need players")
    a, b = players[0], players[1]
    sub, msg = record_submission(st, user_id=a, score=500_000, source="pg", persist=False)
    _assert(sub is not None and sub["verified"] is True, msg)
    sub2, _ = record_submission(st, user_id=a, score=600_000, source="pg", persist=False)
    _assert(sub2 is not None, "second score")
    # best wins
    from rules import best_verified_score

    _assert(best_verified_score(st["submissions"], a, 1) == 600_000, "best replace")
    record_submission(st, user_id=b, score=100_000, source="pg", persist=False)
    team = find_team_by_user(st, a)
    _assert(team is not None, "team")
    rows = standings_rows(st["teams"], st["submissions"], team["division"], through_week=1)
    top = next(r for r in rows if r["team_id"] == team["id"])
    expected = team_week_total(600_000, 100_000 if str(b) in (
        str(team["captain_user_id"]),
        str(team["teammate_user_id"]),
    ) else 0, 1)
    # b is teammate of a by construction (pair)
    _assert(top["total"] == 700_000, f"team total {top['total']} expected 700000 / {expected}")
    _ok("basic open week + best-of")


def scenario_unregistered_and_zero(st: dict[str, Any]) -> None:
    sub, msg = record_submission(st, user_id=999_999_999, score=1_000_000, source="pg", persist=False)
    _assert(sub is None and "not on a registered" in msg.lower(), msg)
    players = _all_player_ids(st)
    subz, msgz = record_submission(st, user_id=players[0], score=0, source="pg", persist=False)
    _assert(subz is None and "greater than zero" in msgz.lower(), msgz)
    subn, _ = record_submission(st, user_id=players[0], score=-5, source="pg", persist=False)
    _assert(subn is None, "negative score rejected")
    # inactive team players
    sub_i, msg_i = record_submission(st, user_id=1, score=50, source="pg", persist=False)
    _assert(sub_i is None, f"inactive should not submit: {msg_i}")
    _ok("unregistered / zero / inactive rejected")


def scenario_message_dedupe(st: dict[str, Any]) -> None:
    uid = _all_player_ids(st)[2]
    mid = 42_424_242
    s1, m1 = record_submission(
        st, user_id=uid, score=111, source="embed", message_id=mid, persist=False
    )
    _assert(s1 is not None and s1["verified"], m1)
    n_before = len(st["submissions"])
    s2, m2 = record_submission(
        st, user_id=uid, score=999_999, source="embed", message_id=mid, persist=False
    )
    _assert(s2 is not None and s2["id"] == s1["id"], m2)
    _assert(len(st["submissions"]) == n_before, "dedupe must not append")
    _assert(int(s2["score"]) == 111, "dedupe keeps original score")
    _assert(find_submission_by_message_id(st, mid) is s1 or find_submission_by_message_id(st, mid)["id"] == s1["id"], "lookup")
    # Different message → new row
    s3, _ = record_submission(
        st, user_id=uid, score=222, source="embed", message_id=mid + 1, persist=False
    )
    _assert(s3 is not None and s3["id"] != s1["id"], "new message new row")
    _ok("message_id dedupe (re-forward safe)")


def scenario_auto_clock() -> None:
    """Season automation: scoring window, evaluate open/close, test-time scale, lifecycle."""
    # --- wall-clock window boundaries (fixed PT dates) ---
    sat_open = datetime(2026, 7, 18, 10, 0, tzinfo=_PT)
    sat_early = datetime(2026, 7, 18, 9, 59, tzinfo=_PT)
    fri_almost = datetime(2026, 7, 24, 23, 58, tzinfo=_PT)
    fri_close = datetime(2026, 7, 24, 23, 59, tzinfo=_PT)
    _assert(in_scoring_window(sat_open), "Sat 10:00 in window")
    _assert(not in_scoring_window(sat_early), "Sat 9:59 out of window")
    _assert(in_scoring_window(fri_almost), "Fri 23:58 still in window")
    _assert(not in_scoring_window(fri_close), "Fri 23:59 closed window")
    _ok("scoring window boundaries")

    # --- pure evaluate_clock ---
    st = empty_state()
    st["weeks"]["1"]["status"] = "scheduled"
    _assert(
        evaluate_clock(st, now=datetime(2026, 7, 18, 10, 5, tzinfo=_PT)) == "open",
        "scheduled + Sat → open",
    )
    st["weeks"]["1"]["status"] = "open"
    _assert(
        evaluate_clock(st, now=datetime(2026, 7, 18, 10, 5, tzinfo=_PT)) is None,
        "already open → no action",
    )
    _assert(
        evaluate_clock(st, now=datetime(2026, 7, 24, 23, 59, tzinfo=_PT)) == "close",
        "open + Fri 23:59 → close",
    )
    st["weeks"]["1"]["status"] = "closed"
    _assert(
        evaluate_clock(st, now=datetime(2026, 7, 24, 23, 59, tzinfo=_PT)) is None,
        "already closed → no reopen same window",
    )
    _ok("evaluate_clock open/close")

    # --- test time: 1 real min = 1 virtual hour ---
    prev_test = config.RS_TEST_TIME
    prev_scale = config.RS_TEST_VHOURS_PER_RMIN
    config.RS_TEST_TIME = True
    config.RS_TEST_VHOURS_PER_RMIN = 1.0
    try:
        st2 = empty_state()
        real0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        ensure_test_origins(st2, anchor="before_open", real_now=real0)
        st2["weeks"]["1"]["status"] = "scheduled"
        v0 = clock_now(st2, real_now=real0)
        _assert(v0.hour == 9 and v0.minute == 50, f"before_open virt {v0}")
        # +10 real minutes → virtual 19:50 same Sat (still before open? wait 9:50+10h=19:50 Sat still in window after 10)
        real_mid = real0 + timedelta(minutes=10)
        v_mid = clock_now(st2, real_now=real_mid)
        _assert(v_mid.hour == 19 and v_mid.minute == 50, f"scale +10min → {v_mid}")
        # +15 real min from 9:50 → 00:50 Sunday? 9:50+15h = 00:50 next day — actually 9:50+15=24:50 → Sun 00:50
        # open decision: need virtual past Sat 10:00 while still scheduled
        real_open = real0 + timedelta(minutes=15)  # virt 00:50 Sun — still in window
        action = evaluate_clock(st2, now=clock_now(st2, real_now=real_open))
        _assert(action == "open", f"test clock should open got {action}")
        open_week(st2, now=real_open)
        _assert(st2["weeks"]["1"]["status"] == "open", "lifecycle open_week")
        _assert((st2.get("auto") or {}).get("last_open_week") == 1, "auto last_open_week")

        # jump to before_close and close
        ensure_test_origins(st2, anchor="before_close", real_now=real0)
        st2["weeks"]["1"]["status"] = "open"
        # +10 real min from Fri 23:50 → Sat 09:50 next? 23:50+10h = 09:50 Sat — after Fri close
        real_after_close = real0 + timedelta(minutes=10)
        action_c = evaluate_clock(st2, now=clock_now(st2, real_now=real_after_close))
        _assert(action_c == "close", f"test clock should close got {action_c}")
        close_week(st2, advance=False, now=real_after_close)
        _assert(st2["weeks"]["1"]["status"] == "closed", "lifecycle close_week")
        nxt = advance_to_next_week(st2, from_week=1)
        _assert(nxt == 2, f"advance to week 2 got {nxt}")
        _assert(st2["season"]["current_week"] == 2, "season.current_week advanced")
        _assert(st2["weeks"]["2"]["status"] == "scheduled", "next week scheduled")
        _ok("test-time scale + open/close lifecycle")
    finally:
        config.RS_TEST_TIME = prev_test
        config.RS_TEST_VHOURS_PER_RMIN = prev_scale

    # --- team import smoke (automation ops path) ---
    from team_import import import_teams

    st3 = empty_state()
    csv = (
        "team_name,division,captain_id,teammate_id\n"
        "PG Auto A,classic,900001,900002\n"
        "PG Auto B,fusion,900003,900004\n"
    )
    ok, err = import_teams(st3, csv)
    _assert(len(ok) == 2 and not err, f"import {ok} {err}")
    _assert(len(st3["teams"]) == 2, "two teams imported")
    _ok("team import for auto season setup")


def scenario_closed_pending_approve(st: dict[str, Any]) -> None:
    uid = _all_player_ids(st)[4]
    st["weeks"]["1"]["status"] = "closed"
    pending, pmsg = record_submission(st, user_id=uid, score=77_000, source="embed", persist=False)
    _assert(pending is not None and pending["verified"] is False, pmsg)
    ok, amsg = approve_submission(st, pending["id"], admin_id=1, persist=False)
    _assert(ok is not None and ok["verified"] is True, amsg)
    from rules import best_verified_score

    _assert(best_verified_score(st["submissions"], uid, 1) == 77_000, "approved counts")
    # staff force while closed
    ok2, _ = record_submission(
        st, user_id=uid, score=80_000, source="admin", verified=True, approved_by=1, persist=False
    )
    _assert(ok2 is not None and ok2["verified"] is True, "staff verified")
    _assert(best_verified_score(st["submissions"], uid, 1) == 80_000, "staff higher best")
    st["weeks"]["1"]["status"] = "open"
    _ok("closed week pending + approve + staff set")


def scenario_captain_burden_full_season(st: dict[str, Any]) -> None:
    """Drive a dedicated classic team through weeks 1–4 with burden math.

    Uses reserved user ids so earlier playground scores cannot pollute totals.
    """
    cap, mate = 700_001, 700_002
    team = {
        "id": "burden-lab",
        "name": "Burden Lab",
        "division": "classic",
        "captain_user_id": str(cap),
        "teammate_user_id": str(mate),
        "active": True,
    }
    # Replace if re-run mid-session
    st["teams"] = [t for t in st["teams"] if t.get("id") != "burden-lab"]
    st["teams"].append(team)
    # Drop any prior subs for these users
    st["submissions"] = [
        s
        for s in st.get("submissions") or []
        if str(s.get("user_id")) not in (str(cap), str(mate))
    ]

    plan = {
        1: (1000, 500),
        2: (2000, 600),
        3: (1500, 700),
        4: (3000, 1000),  # burden: 3000 + 2000 = 5000
    }
    for week, (cs, ms) in plan.items():
        st["season"]["current_week"] = week
        st["weeks"][str(week)]["status"] = "open"
        st["weeks"][str(week)]["song_title"] = f"Week {week} Song"
        record_submission(st, user_id=cap, score=cs, source="pg-burden", persist=False)
        record_submission(st, user_id=mate, score=ms, source="pg-burden", persist=False)
        st["weeks"][str(week)]["status"] = "closed"

    total = team_season_total(st["submissions"], cap, mate, through_week=4)
    # w1 1500 + w2 2600 + w3 2200 + w4 5000 = 11300
    _assert(total == 11_300, f"season total {total} != 11300")
    rows = standings_rows(st["teams"], st["submissions"], "classic", through_week=4)
    hit = next(r for r in rows if r["team_id"] == team["id"])
    _assert(hit["total"] == 11_300, "standings match season total")
    # reset week pointer for later floods
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    _ok("Captain's Burden full season totals")


def scenario_division_isolation(st: dict[str, Any]) -> None:
    """Huge classic scores must not appear in fusion standings."""
    classic_team = next(t for t in st["teams"] if t.get("active") and t["division"] == "classic")
    fusion_rows = standings_rows(st["teams"], st["submissions"], "fusion", through_week=4)
    for r in fusion_rows:
        _assert(r["team_id"] != classic_team["id"], "classic team leaked into fusion")
    # inactive never listed
    classic_rows = standings_rows(st["teams"], st["submissions"], "classic", through_week=4)
    names = {r["name"] for r in classic_rows}
    _assert("Bench Warmers" not in names, "inactive team in standings")
    _ok("division isolation + inactive hidden")


def scenario_embed_parse() -> None:
    import discord

    emb = discord.Embed(title="ignored", description="Artist: Test Band")
    emb.add_field(name="Song", value="Playground Anthem")
    emb.add_field(name="Score", value="1,234,567")
    emb.add_field(name="Difficulty", value="Extreme")
    emb.add_field(name="Game Mode", value="Classic")
    emb.set_author(name="DrummerDude (Quest)")
    data = parse_embed(emb)
    _assert(data is not None, "parse failed")
    _assert(data["score"] == 1_234_567, f"score {data.get('score')}")
    _assert(data["gameMode"] == "classic", f"mode {data.get('gameMode')}")
    _assert(data["difficulty"] == "extreme", f"diff {data.get('difficulty')}")
    _assert(data["playerName"] == "DrummerDude", f"name {data.get('playerName')}")
    _ok("Smash Drums-like embed parse")


def scenario_score_flood(st: dict[str, Any], n: int, *, persist_each: bool = False) -> dict[str, Any]:
    """Flood submissions like a busy Saturday night."""
    players = _all_player_ids(st)
    _assert(players, "no players")
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    rng = random.Random(7)
    t0 = time.perf_counter()
    accepted = 0
    rejected = 0
    for i in range(n):
        # 5% noise: unregistered
        if rng.random() < 0.05:
            sub, _ = record_submission(
                st,
                user_id=rng.randint(50_000_000, 60_000_000),
                score=rng.randint(1, 999_999),
                source="flood",
                message_id=None if not persist_each else None,
                persist=persist_each,
            )
            if sub is None:
                rejected += 1
            continue
        uid = players[rng.randrange(len(players))]
        score = rng.randint(1, 2_000_000)
        mid = 1_000_000 + i  # unique message ids
        # 10% deliberate re-forwards of a previous message id
        if i > 10 and rng.random() < 0.10:
            mid = 1_000_000 + rng.randint(0, i - 1)
        sub, _ = record_submission(
            st,
            user_id=uid,
            score=score,
            source="flood",
            message_id=mid,
            persist=persist_each,
        )
        if sub is None:
            rejected += 1
        else:
            accepted += 1
    elapsed = time.perf_counter() - t0
    # Standings for all divisions still computable
    t1 = time.perf_counter()
    totals = {}
    for div in ("classic", "fusion", "arcade"):
        rows = standings_rows(st["teams"], st["submissions"], div, through_week=1)
        totals[div] = len(rows)
        # ranks unique contiguous
        ranks = [r["rank"] for r in rows]
        _assert(ranks == list(range(1, len(rows) + 1)), f"{div} ranks broken")
        # sorted desc
        scores = [r["total"] for r in rows]
        _assert(scores == sorted(scores, reverse=True), f"{div} sort broken")
    standings_ms = (time.perf_counter() - t1) * 1000
    stats = {
        "n": n,
        "accepted": accepted,
        "rejected": rejected,
        "subs_len": len(st["submissions"]),
        "flood_sec": elapsed,
        "standings_ms": standings_ms,
        "rows": totals,
    }
    _ok(
        f"flood n={n} accepted={accepted} rejected={rejected} "
        f"subs={stats['subs_len']} in {elapsed:.3f}s · standings {standings_ms:.1f}ms"
    )
    return stats


def scenario_disk_roundtrip(st: dict[str, Any], path: Path) -> None:
    _patch_state_path(path)
    save_state(st)
    loaded = load_state()
    _assert(len(loaded.get("teams") or []) == len(st["teams"]), "teams lost")
    _assert(len(loaded.get("submissions") or []) == len(st["submissions"]), "subs lost")
    # standings stable after reload
    for div in ("classic", "fusion", "arcade"):
        a = standings_rows(st["teams"], st["submissions"], div, through_week=4)
        b = standings_rows(loaded["teams"], loaded["submissions"], div, through_week=4)
        _assert([r["total"] for r in a] == [r["total"] for r in b], f"{div} totals diverge after load")
    _ok(f"disk round-trip ({path.name}, {path.stat().st_size:,} bytes)")


def scenario_concurrent_saves(path: Path, threads: int = 8, each: int = 40) -> None:
    """Multiple threads calling save_state — final file must be valid JSON."""
    _patch_state_path(path)
    st = empty_state()
    st["teams"] = [
        {
            "id": "t1",
            "name": "Race",
            "division": "classic",
            "captain_user_id": "100",
            "teammate_user_id": "101",
            "active": True,
        }
    ]
    st["weeks"]["1"]["status"] = "open"
    lock = threading.Lock()
    errors: list[str] = []

    def worker(wid: int) -> None:
        try:
            for i in range(each):
                with lock:
                    # mutate under lock like single-process asyncio serializes events
                    record_submission(
                        st,
                        user_id=100 if i % 2 == 0 else 101,
                        score=1000 + wid * 100 + i,
                        source="race",
                        message_id=wid * 10_000 + i,
                        persist=True,
                    )
        except Exception as e:
            errors.append(f"{wid}: {e}")

    ts = [threading.Thread(target=worker, args=(w,)) for w in range(threads)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    elapsed = time.perf_counter() - t0
    _assert(not errors, f"thread errors: {errors[:3]}")
    loaded = load_state()
    _assert(isinstance(loaded.get("submissions"), list), "corrupt submissions")
    # Every unique message should be present
    expected = threads * each
    _assert(len(loaded["submissions"]) == expected, f"subs {len(loaded['submissions'])} != {expected}")
    _ok(f"concurrent saves threads={threads} each={each} in {elapsed:.3f}s · file ok")


def scenario_week_open_close_churn(st: dict[str, Any]) -> None:
    """Staff opens/closes repeatedly while scores land."""
    uid = _all_player_ids(st)[0]
    st["season"]["current_week"] = 2
    for cycle in range(5):
        st["weeks"]["2"]["status"] = "open"
        record_submission(
            st, user_id=uid, score=10_000 + cycle, source="churn", message_id=900_000 + cycle, persist=False
        )
        st["weeks"]["2"]["status"] = "closed"
        p, _ = record_submission(
            st,
            user_id=uid,
            score=1 + cycle,
            source="churn",
            message_id=910_000 + cycle,
            persist=False,
        )
        _assert(p is not None and p["verified"] is False, "should be pending when closed")
    from rules import best_verified_score

    _assert(best_verified_score(st["submissions"], uid, 2) == 10_004, "best open-week score")
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    _ok("week open/close churn")


def scenario_tie_break_names(st: dict[str, Any]) -> None:
    """Equal totals → stable name order."""
    # Two synthetic teams same division identical scores
    st["teams"].append(
        {
            "id": "tie-a",
            "name": "Zebra",
            "division": "classic",
            "captain_user_id": "8001",
            "teammate_user_id": "8002",
            "active": True,
        }
    )
    st["teams"].append(
        {
            "id": "tie-b",
            "name": "Aardvark",
            "division": "classic",
            "captain_user_id": "8003",
            "teammate_user_id": "8004",
            "active": True,
        }
    )
    st["season"]["current_week"] = 3
    st["weeks"]["3"]["status"] = "open"
    for uid in (8001, 8002, 8003, 8004):
        record_submission(st, user_id=uid, score=50_000, source="tie", persist=False)
    rows = standings_rows(st["teams"], st["submissions"], "classic", through_week=3)
    tied = [r for r in rows if r["total"] == 100_000 and r["name"] in ("Zebra", "Aardvark")]
    _assert(len(tied) == 2, "need both tied teams")
    names = [r["name"] for r in rows if r["name"] in ("Zebra", "Aardvark")]
    _assert(names == ["Aardvark", "Zebra"], f"name sort {names}")
    st["season"]["current_week"] = 1
    _ok("tie-break alphabetical by name")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_playground(*, teams_per_div: int, flood: int, skip_threads: bool) -> int:
    print("=" * 60)
    print(f"RS TOURNEY PLAYGROUND  BOT_VERSION={config.BOT_VERSION}")
    print("=" * 60)
    failures = 0

    with tempfile.TemporaryDirectory(prefix="rs_pg_") as tmp:
        tmp_path = Path(tmp)
        playground_state = tmp_path / "rs_state_playground.json"
        race_state = tmp_path / "rs_state_race.json"
        _patch_state_path(playground_state)

        st = _make_season(teams_per_div=teams_per_div)
        print(f"Season seed: {len([t for t in st['teams'] if t.get('active')])} active teams "
              f"({teams_per_div}/div × 3) + 1 inactive")

        scenarios = [
            ("auto clock / test-time", lambda: scenario_auto_clock()),
            ("embed parse", lambda: scenario_embed_parse()),
            ("basic open week", lambda: scenario_basic_open_week(st)),
            ("unregistered/zero/inactive", lambda: scenario_unregistered_and_zero(st)),
            ("message dedupe", lambda: scenario_message_dedupe(st)),
            ("closed pending approve", lambda: scenario_closed_pending_approve(st)),
            ("captain burden season", lambda: scenario_captain_burden_full_season(st)),
            ("division isolation", lambda: scenario_division_isolation(st)),
            ("open/close churn", lambda: scenario_week_open_close_churn(st)),
            ("tie-break names", lambda: scenario_tie_break_names(st)),
            ("score flood", lambda: scenario_score_flood(st, flood, persist_each=False)),
            ("disk round-trip", lambda: scenario_disk_roundtrip(st, playground_state)),
        ]
        if not skip_threads:
            scenarios.append(
                ("concurrent saves", lambda: scenario_concurrent_saves(race_state, threads=8, each=25))
            )

        for name, fn in scenarios:
            print(f"\n[{name}]")
            try:
                fn()
            except _Fail as e:
                failures += 1
                print(f"  FAIL  {e}")
            except Exception:
                failures += 1
                print(f"  FAIL  exception:\n{traceback.format_exc()}")

        # Final snapshot for human inspection
        out = config.PROJECT_DIR / "data" / "rs_state_playground.json"
        try:
            _patch_state_path(out)
            save_state(st)
            print(f"\nPlayground state snapshot → {out}")
            print(f"  submissions: {len(st['submissions']):,}")
            print(f"  teams: {len(st['teams'])}")
            for div in ("classic", "fusion", "arcade"):
                rows = standings_rows(st["teams"], st["submissions"], div, through_week=4)
                if rows:
                    print(f"  {div} #1: {rows[0]['name']} · {rows[0]['total']:,}")
        except OSError as e:
            print(f"\n(snapshot skip: {e})")

    print("\n" + "=" * 60)
    if failures:
        print(f"PLAYGROUND FAILED  ({failures} scenario(s))")
        return 1
    print("PLAYGROUND ALL PASSED")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="RS Tourney offline playground / stress")
    p.add_argument("--teams", type=int, default=10, help="teams per division (default 10)")
    p.add_argument("--flood", type=int, default=3000, help="flood submission count (default 3000)")
    p.add_argument("--skip-threads", action="store_true", help="skip concurrent save stress")
    args = p.parse_args()
    raise SystemExit(
        run_playground(
            teams_per_div=max(2, args.teams),
            flood=max(50, args.flood),
            skip_threads=args.skip_threads,
        )
    )


if __name__ == "__main__":
    main()
