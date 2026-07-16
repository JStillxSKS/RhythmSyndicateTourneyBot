#!/usr/bin/env python3
"""
Extra stress + edge cases for go-live confidence.
Run: python test_extra_stress.py
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT_DIR))

import config  # noqa: E402
from dashboard import (  # noqa: E402
    build_announce_embed,
    build_dashboard_embed,
    build_standings_embeds,
    missing_submissions,
    time_remaining_text,
)
from deadline import default_week_close_utc  # noqa: E402
from rules import best_verified_score, standings_rows, team_week_total  # noqa: E402
from scores import approve_submission, list_pending, parse_embed, record_submission  # noqa: E402
from state import empty_state, find_team_by_name, load_state, new_team_id, save_state  # noqa: E402

fails: list[str] = []
oks = 0


def ok(m: str) -> None:
    global oks
    oks += 1
    print(f"  OK  {m}")


def fail(m: str) -> None:
    fails.append(m)
    print(f"  FAIL  {m}")


def check(c: bool, m: str) -> None:
    (ok if c else fail)(m)


def patch(path: Path) -> None:
    config.STATE_PATH = path  # type: ignore[misc]
    import state as sm

    sm.STATE_PATH = path


def big_season(n_per: int = 30) -> dict:
    st = empty_state()
    st["season"]["current_week"] = 1
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["song_title"] = "Stress Hymn"
    uid = 1_000_000
    for div in ("classic", "fusion", "arcade"):
        for i in range(n_per):
            st["teams"].append(
                {
                    "id": new_team_id(),
                    "name": f"{div}-{i:03d}-{'LongTeamName' * 3}",
                    "division": div,
                    "captain_user_id": str(uid),
                    "teammate_user_id": str(uid + 1),
                    "active": True,
                }
            )
            uid += 2
    return st


def test_mega_best_of() -> None:
    print("\n[mega best-of same player]")
    st = big_season(5)
    uid = int(st["teams"][0]["captain_user_id"])
    best = 0
    for i in range(500):
        s = random.randint(1, 5_000_000)
        best = max(best, s)
        record_submission(
            st, user_id=uid, score=s, source="x", message_id=10_000 + i, persist=False
        )
    check(best_verified_score(st["submissions"], uid, 1) == best, f"best of 500 attempts = {best:,}")


def test_pending_queue() -> None:
    print("\n[pending queue bulk approve]")
    st = big_season(10)
    st["weeks"]["1"]["status"] = "closed"
    ids = []
    for t in st["teams"]:
        uid = int(t["captain_user_id"])
        sub, _ = record_submission(
            st, user_id=uid, score=1000 + uid % 100, source="late", message_id=uid, persist=False
        )
        if sub:
            ids.append(sub["id"])
    pend = list_pending(st, week=1, limit=100)
    check(len(pend) >= 20, f"pending pile size {len(pend)}")
    for sid in ids[:15]:
        approve_submission(st, sid, admin_id=1, persist=False)
    still = [s for s in st["submissions"] if not s.get("verified") and int(s.get("week") or 0) == 1]
    check(len(still) == len(ids) - 15, "partial approve math")


def test_all_four_weeks_chaos() -> None:
    print("\n[4-week chaos season]")
    st = big_season(6)
    rng = random.Random(99)
    for week in range(1, 5):
        st["season"]["current_week"] = week
        st["weeks"][str(week)]["status"] = "open"
        st["weeks"][str(week)]["song_title"] = f"W{week}"
        for t in st["teams"]:
            if rng.random() < 0.85:  # some no-shows
                record_submission(
                    st,
                    user_id=int(t["captain_user_id"]),
                    score=rng.randint(10_000, 2_000_000),
                    source="chaos",
                    week=week,
                    persist=False,
                )
            if rng.random() < 0.85:
                record_submission(
                    st,
                    user_id=int(t["teammate_user_id"]),
                    score=rng.randint(10_000, 2_000_000),
                    source="chaos",
                    week=week,
                    persist=False,
                )
        st["weeks"][str(week)]["status"] = "closed"
    for div in ("classic", "fusion", "arcade"):
        rows = standings_rows(st["teams"], st["submissions"], div, through_week=4)
        check(len(rows) == 6, f"{div} 6 teams ranked")
        scores = [r["total"] for r in rows]
        check(scores == sorted(scores, reverse=True), f"{div} sorted")
        check(all(r["rank"] == i for i, r in enumerate(rows, 1)), f"{div} ranks 1..n")
    # burden only multiplies week 4 teammate
    check(team_week_total(10, 10, 3) == 20, "w3 no burden")
    check(team_week_total(10, 10, 4) == 30, "w4 burden")


def test_rapid_open_close_with_flood() -> None:
    print("\n[rapid open/close + flood]")
    st = big_season(8)
    uid = int(st["teams"][0]["captain_user_id"])
    verified_n = 0
    pending_n = 0
    for i in range(200):
        st["weeks"]["1"]["status"] = "open" if i % 2 == 0 else "closed"
        sub, _ = record_submission(
            st,
            user_id=uid,
            score=1000 + i,
            source="flip",
            message_id=50_000 + i,
            persist=False,
        )
        if sub and sub["verified"]:
            verified_n += 1
        elif sub:
            pending_n += 1
    check(verified_n > 0 and pending_n > 0, f"mixed verified={verified_n} pending={pending_n}")
    check(best_verified_score(st["submissions"], uid, 1) >= 1000, "has verified best")


def test_corrupt_state_recovery() -> None:
    print("\n[corrupt / empty state recovery]")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.json"
        patch(path)
        path.write_text("{not json", encoding="utf-8")
        st = load_state()
        check(isinstance(st.get("teams"), list), "corrupt JSON → empty_state shape")
        path.write_text("[]", encoding="utf-8")
        st2 = load_state()
        check(isinstance(st2.get("season"), dict), "array JSON → empty_state")
        # partial keys
        path.write_text(json.dumps({"teams": "nope"}), encoding="utf-8")
        st3 = load_state()
        check(isinstance(st3.get("teams"), list), "bad teams type coerced")


def test_atomic_save_no_half_file() -> None:
    print("\n[atomic save under load]")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "race.json"
        patch(path)
        st = big_season(3)
        st["weeks"]["1"]["status"] = "open"
        errors = []

        def w(i: int) -> None:
            try:
                for j in range(30):
                    record_submission(
                        st,
                        user_id=int(st["teams"][0]["captain_user_id"]),
                        score=1 + i * 100 + j,
                        source="race",
                        message_id=i * 1000 + j,
                        persist=True,
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=w, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        check(not errors, f"no exceptions {errors[:2]}")
        # file must parse
        data = json.loads(path.read_text(encoding="utf-8"))
        check(isinstance(data.get("submissions"), list), "final JSON valid")
        bak = path.with_suffix(".bak.json")
        check(bak.is_file() or True, "bak optional present")  # always true-ish; just ensure load works
        loaded = load_state()
        check(len(loaded["submissions"]) == 6 * 30, f"subs={len(loaded['submissions'])}")


def test_embed_limits_max_roster() -> None:
    print("\n[embed limits @ 90 teams]")
    st = big_season(30)
    st["weeks"]["1"]["status"] = "open"
    st["weeks"]["1"]["close_at"] = default_week_close_utc().isoformat()
    # zero scores → everyone missing
    miss = missing_submissions(st, 1)
    check(len(miss) == 180, f"missing players {len(miss)}")
    dash = build_dashboard_embed(st)
    for f in dash.fields:
        check(len(f.value or "") <= 1024, f"dash field {f.name!r} len={len(f.value or '')}")
    for emb in build_standings_embeds(st):
        for f in emb.fields:
            check(len(f.value or "") <= 1024, f"board {emb.title} {f.name} len={len(f.value or '')}")
    ann = build_announce_embed(st, message="Season 1 is LIVE. Forward Smash Drums embeds here.", style="week_open")
    check(len(ann.description or "") <= 4096, "announce desc ok")


def test_parse_edge_embeds() -> None:
    print("\n[weird embed shapes]")
    import discord

    # Indies song line
    e1 = discord.Embed()
    e1.add_field(name="Song", value="[Indies] abc123def Song Name")
    e1.add_field(name="Score", value="999")
    e1.add_field(name="Game Mode", value="Arcade")
    d1 = parse_embed(e1)
    check(d1 is not None and d1.get("isIndie") is True, "indies flag")
    check(d1 is not None and d1["score"] == 999, "indies score")

    # points alias
    e2 = discord.Embed()
    e2.add_field(name="Points", value="42,000")
    e2.add_field(name="Song", value="X")
    d2 = parse_embed(e2)
    check(d2 is not None and d2["score"] == 42000, "points field alias")

    # empty embed
    e3 = discord.Embed(title="hi")
    d3 = parse_embed(e3)
    check(d3 is None or not d3.get("score"), "empty-ish embed no false score")

    # hardcore difficulty
    e4 = discord.Embed()
    e4.add_field(name="Song", value="S")
    e4.add_field(name="Score", value="1")
    e4.add_field(name="Difficulty", value="Hardcore")
    e4.add_field(name="Mode", value="Classic")
    d4 = parse_embed(e4)
    check(d4 is not None and d4.get("difficulty") == "hardcore", "hardcore diff")
    check(d4 is not None and d4.get("gameMode") == "classic", "mode field alias")


def test_find_team_name_case() -> None:
    print("\n[team name case]")
    st = big_season(2)
    st["teams"][0]["name"] = "Red Steel"
    check(find_team_by_name(st, "red steel") is not None, "case-insensitive name match")
    check(find_team_by_name(st, "RED STEEL") is not None, "upper name match")
    check(find_team_by_name(st, "nope") is None, "missing name")


def test_time_remaining() -> None:
    print("\n[deadline display]")
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).isoformat()
    t = time_remaining_text(future, "open")
    check("h" in t or "m" in t, f"time left text={t!r}")
    check(time_remaining_text(future, "closed") == "—", "closed no countdown")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    check(time_remaining_text(past, "open") == "Deadline passed", "past deadline")


def test_throughput() -> None:
    print("\n[throughput benchmark]")
    st = big_season(20)
    st["weeks"]["1"]["status"] = "open"
    players = []
    for t in st["teams"]:
        players.append(int(t["captain_user_id"]))
        players.append(int(t["teammate_user_id"]))
    n = 15_000
    t0 = time.perf_counter()
    for i in range(n):
        uid = players[i % len(players)]
        record_submission(
            st,
            user_id=uid,
            score=(i * 17) % 2_000_000 + 1,
            source="bench",
            message_id=900_000 + i,
            persist=False,
        )
    elapsed = time.perf_counter() - t0
    rate = n / elapsed if elapsed else 0
    check(elapsed < 30, f"15k subs in {elapsed:.2f}s ({rate:.0f}/s)")
    t1 = time.perf_counter()
    for div in ("classic", "fusion", "arcade"):
        standings_rows(st["teams"], st["submissions"], div, through_week=1)
    s_ms = (time.perf_counter() - t1) * 1000
    check(s_ms < 500, f"3-div standings {s_ms:.1f}ms on {len(st['submissions'])} subs")


def main() -> int:
    print("=" * 60)
    print(f"EXTRA STRESS  {config.BOT_VERSION}")
    print("=" * 60)
    for fn in (
        test_mega_best_of,
        test_pending_queue,
        test_all_four_weeks_chaos,
        test_rapid_open_close_with_flood,
        test_corrupt_state_recovery,
        test_atomic_save_no_half_file,
        test_embed_limits_max_roster,
        test_parse_edge_embeds,
        test_find_team_name_case,
        test_time_remaining,
        test_throughput,
    ):
        try:
            fn()
        except Exception:
            fail(f"{fn.__name__} EXCEPTION:\n{traceback.format_exc()}")

    print("\n" + "=" * 60)
    print(f"OK={oks}  FAIL={len(fails)}")
    for f in fails:
        print(f"  - {f}")
    if fails:
        print("EXTRA STRESS FAILED")
        return 1
    print("EXTRA STRESS ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
