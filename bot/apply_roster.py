"""
Build team list + Discord /rs commands from filled DISCORD_SMASH_NAME_MAP.csv
or roster_poster_season1.json (with discord_id filled).

Usage (from repo root or bot/):
  python bot/apply_roster.py
  python bot/apply_roster.py --write-state   # write data/rs_state.json teams (needs all IDs)

Does not call Discord. For live bot: paste import CSV into /rs team import,
or run the printed /rs team add lines in Discord.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CSV_PATH = DATA / "DISCORD_SMASH_NAME_MAP.csv"
JSON_PATH = DATA / "roster_poster_season1.json"
STATE_PATH = DATA / "rs_state.json"


def load_from_csv() -> list[dict]:
    if not CSV_PATH.is_file():
        return []
    by_team: dict[str, dict] = {}
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("team_name") or "").strip()
            if not name:
                continue
            t = by_team.setdefault(
                name,
                {
                    "name": name,
                    "division": (row.get("division") or "").strip().lower(),
                    "players": [],
                },
            )
            t["players"].append(
                {
                    "slot": (row.get("slot") or "captain").strip().lower(),
                    "display": (row.get("display_on_poster") or "").strip(),
                    "discord_username": (row.get("discord_username") or "").strip(),
                    "discord_id": (row.get("discord_id") or "").strip() or None,
                    "smash_name": (row.get("smash_drums_name") or "").strip() or None,
                }
            )
    return list(by_team.values())


def load_from_json() -> list[dict]:
    if not JSON_PATH.is_file():
        return []
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return list(data.get("teams") or [])


def captain_mate(team: dict) -> tuple[dict | None, dict | None]:
    cap = mate = None
    for p in team.get("players") or []:
        slot = (p.get("slot") or "").lower()
        if slot in ("captain", "captain_a", "a"):
            cap = p
        elif slot in ("teammate", "captain_b", "b"):
            mate = p
    if cap is None and team.get("players"):
        cap = team["players"][0]
    if mate is None and len(team.get("players") or []) > 1:
        mate = team["players"][1]
    return cap, mate


def all_ids_ready(teams: list[dict]) -> bool:
    for t in teams:
        div = (t.get("division") or "").lower()
        cap, mate = captain_mate(t)
        if not cap or not cap.get("discord_id"):
            return False
        if div != "fusion" and (not mate or not mate.get("discord_id")):
            return False
    return True


def print_status(teams: list[dict]) -> None:
    print(f"Teams: {len(teams)}")
    missing = 0
    for t in teams:
        cap, mate = captain_mate(t)
        def label(p: dict | None) -> str:
            if not p:
                return "(none)"
            did = p.get("discord_id") or "NO_ID"
            sm = p.get("smash_name") or "NO_SMASH"
            return f"{p.get('display')} id={did} smash={sm}"

        print(f"  [{t.get('division')}] {t.get('name')}")
        print(f"      captain:  {label(cap)}")
        if (t.get("division") or "").lower() != "fusion" or mate:
            print(f"      teammate: {label(mate)}")
        if not cap or not cap.get("discord_id"):
            missing += 1
        if (t.get("division") or "").lower() != "fusion" and (not mate or not mate.get("discord_id")):
            missing += 1
    print(f"Missing discord_id slots: {missing}")


def print_import_csv(teams: list[dict]) -> None:
    print("\n--- paste into /rs team import (only rows with IDs) ---")
    print("team_name,division,captain_id,teammate_id")
    for t in teams:
        cap, mate = captain_mate(t)
        cid = (cap or {}).get("discord_id") or ""
        mid = (mate or {}).get("discord_id") or ""
        if not cid:
            continue
        if (t.get("division") or "").lower() != "fusion" and not mid:
            continue
        print(f"{t['name']},{t['division']},{cid},{mid}")


def write_state(teams: list[dict]) -> None:
    from state import empty_state, save_state, new_team_id  # type: ignore

    # ensure STATE_PATH
    import state as state_mod

    st = empty_state()
    if STATE_PATH.is_file():
        st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    st["teams"] = []
    for t in teams:
        cap, mate = captain_mate(t)
        if not cap or not cap.get("discord_id"):
            raise SystemExit(f"Missing captain id for {t.get('name')}")
        div = (t.get("division") or "").lower()
        if div != "fusion" and (not mate or not mate.get("discord_id")):
            raise SystemExit(f"Missing teammate id for {t.get('name')}")
        st["teams"].append(
            {
                "id": new_team_id(),
                "name": t["name"],
                "division": div,
                "captain_user_id": str(cap["discord_id"]),
                "teammate_user_id": str(mate["discord_id"]) if mate and mate.get("discord_id") else None,
                "active": True,
                "players_meta": [
                    {
                        "slot": p.get("slot"),
                        "display": p.get("display"),
                        "smash_name": p.get("smash_name"),
                        "discord_id": p.get("discord_id"),
                    }
                    for p in (t.get("players") or [])
                ],
            }
        )
    # prefer module save
    state_mod.STATE_PATH = STATE_PATH  # type: ignore
    save_state(st)
    print(f"Wrote {len(st['teams'])} teams → {STATE_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-state", action="store_true")
    ap.add_argument("--from-json", action="store_true", help="Prefer JSON roster over CSV")
    args = ap.parse_args()

    teams = load_from_json() if args.from_json else load_from_csv()
    if not teams:
        teams = load_from_json() or load_from_csv()
    if not teams:
        print("No roster data found.", file=sys.stderr)
        sys.exit(1)

    print_status(teams)
    print_import_csv(teams)

    if args.write_state:
        if not all_ids_ready(teams):
            print("\nCannot write state until every required discord_id is filled.", file=sys.stderr)
            sys.exit(2)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        write_state(teams)
    else:
        print("\nFill data/DISCORD_SMASH_NAME_MAP.csv (discord_id + smash_drums_name),")
        print("then re-run. When IDs complete: python bot/apply_roster.py --write-state")
        print("Live Discord: /rs team import with the CSV block above, or /rs team add per ADD_TEAMS_NOW.md")


if __name__ == "__main__":
    main()
