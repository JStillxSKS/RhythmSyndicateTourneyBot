"""
Season 1 fixed roster — teams do not change for 4 weeks.

Loads data/season1_fixed_roster.json into state on startup (and on demand).
Merges by stable team id/name; does not wipe submissions.

After Discord/Smash name map is filled into the fixed file, scoring can use:
  - Discord user id on captain/teammate slots, and/or
  - Smash / display name match from the score embed (playerName).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import STATE_PATH

ROSTER_PATH = STATE_PATH.parent / "season1_fixed_roster.json"


def _norm_name(s: str | None) -> str:
    if not s:
        return ""
    t = s.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _player_aliases(p: dict[str, Any] | None) -> list[str]:
    if not p:
        return []
    out: list[str] = []
    for key in ("smash_name", "display", "discord_username"):
        v = p.get(key)
        if v:
            out.append(str(v))
    for a in p.get("aka") or []:
        if a:
            out.append(str(a))
    return out


def _slot_to_ids(p: dict[str, Any] | None) -> str | None:
    if not p:
        return None
    did = p.get("discord_id")
    if did is None or str(did).strip() == "":
        return None
    return str(int(str(did).strip())) if str(did).strip().isdigit() else str(did).strip()


def load_fixed_roster_file() -> list[dict[str, Any]]:
    if not ROSTER_PATH.is_file():
        return []
    try:
        data = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARNING: fixed roster read failed: {e}")
        return []
    return list(data.get("teams") or [])


def roster_entry_to_state_team(entry: dict[str, Any]) -> dict[str, Any]:
    cap = entry.get("captain") or {}
    mate = entry.get("teammate")
    return {
        "id": entry.get("id") or f"s1-{(entry.get('name') or 'team').lower().replace(' ', '-')}",
        "name": entry.get("name"),
        "division": (entry.get("division") or "").lower().strip(),
        "captain_user_id": _slot_to_ids(cap),
        "teammate_user_id": _slot_to_ids(mate) if mate else None,
        "active": True,
        "locked": True,
        "roster": {
            "captain": {
                "display": cap.get("display"),
                "smash_name": cap.get("smash_name") or cap.get("display"),
                "discord_id": _slot_to_ids(cap),
                "aka": list(cap.get("aka") or []),
            },
            "teammate": (
                {
                    "display": mate.get("display"),
                    "smash_name": mate.get("smash_name") or mate.get("display"),
                    "discord_id": _slot_to_ids(mate),
                    "aka": list(mate.get("aka") or []),
                }
                if mate
                else None
            ),
        },
    }


def ensure_fixed_roster(state: dict[str, Any], *, persist: bool = False) -> dict[str, Any]:
    """
    Ensure Season 1 poster teams exist in state.
    - If a locked team id/name is missing → add it
    - If present → refresh roster metadata / ids from file (IDs only overwrite when file has a value)
    Does not remove other teams or submissions.
    """
    from state import save_state

    entries = load_fixed_roster_file()
    if not entries:
        return state

    teams = list(state.get("teams") or [])
    by_id = {str(t.get("id")): t for t in teams if t.get("id")}
    by_name = {(t.get("name") or "").strip().lower(): t for t in teams}

    changed = False
    for entry in entries:
        desired = roster_entry_to_state_team(entry)
        tid = str(desired["id"])
        nkey = (desired.get("name") or "").strip().lower()
        existing = by_id.get(tid) or by_name.get(nkey)
        if existing is None:
            teams.append(desired)
            by_id[tid] = desired
            by_name[nkey] = desired
            changed = True
            continue
        # Merge: keep submissions linkage; update ids when seed has them
        if desired.get("captain_user_id"):
            if existing.get("captain_user_id") != desired["captain_user_id"]:
                existing["captain_user_id"] = desired["captain_user_id"]
                changed = True
        if desired.get("teammate_user_id") is not None:
            if existing.get("teammate_user_id") != desired["teammate_user_id"]:
                existing["teammate_user_id"] = desired["teammate_user_id"]
                changed = True
        if desired.get("teammate_user_id") is None and (entry.get("teammate") is None):
            # fusion solo — clear mate if seed says solo
            if existing.get("teammate_user_id"):
                # only clear if seed has no mate person at all
                pass
        existing["locked"] = True
        existing["division"] = desired.get("division") or existing.get("division")
        existing["name"] = desired.get("name") or existing.get("name")
        existing["roster"] = desired.get("roster")
        existing["active"] = True
        changed = True

    state["teams"] = teams
    state["roster_locked"] = True
    if persist and changed:
        save_state(state)
    if changed:
        print(f"FIXED ROSTER: ensured {len(entries)} Season 1 teams (ids may still be pending)")
    return state


def _name_hits(player_name: str, slot: dict[str, Any] | None) -> bool:
    if not slot or not player_name:
        return False
    target = _norm_name(player_name)
    if not target:
        return False
    for alias in _player_aliases(slot):
        a = _norm_name(alias)
        if not a:
            continue
        if a == target or a in target or target in a:
            return True
    return False


def find_team_by_smash_or_display(
    state: dict[str, Any], player_name: str | None
) -> dict[str, Any] | None:
    """Match score embed player name to fixed roster smash/display/aka."""
    if not player_name:
        return None
    for t in state.get("teams") or []:
        if not t.get("active", True):
            continue
        roster = t.get("roster") or {}
        if _name_hits(player_name, roster.get("captain")):
            return t
        if _name_hits(player_name, roster.get("teammate")):
            return t
        # fallback: bare display fields if roster block missing
        if _name_hits(player_name, {"display": t.get("name"), "smash_name": None, "aka": []}):
            continue
    return None


def apply_csv_map_to_fixed_roster(csv_path: Path | None = None) -> int:
    """Optional: merge DISCORD_SMASH_NAME_MAP.csv into season1_fixed_roster.json."""
    import csv

    from config import STATE_PATH

    path = csv_path or (STATE_PATH.parent / "DISCORD_SMASH_NAME_MAP.csv")
    if not path.is_file() or not ROSTER_PATH.is_file():
        return 0
    data = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    teams = {t["name"].strip().lower(): t for t in data.get("teams") or []}
    updated = 0
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tname = (row.get("team_name") or "").strip().lower()
            slot = (row.get("slot") or "captain").strip().lower()
            t = teams.get(tname)
            if not t:
                continue
            key = "captain" if slot.startswith("captain") else "teammate"
            if key == "teammate" and t.get("teammate") is None:
                continue
            person = t.get(key) or {}
            did = (row.get("discord_id") or "").strip()
            smash = (row.get("smash_drums_name") or "").strip()
            duser = (row.get("discord_username") or "").strip()
            if did:
                person["discord_id"] = did
                updated += 1
            if smash:
                person["smash_name"] = smash
                updated += 1
            if duser:
                person["discord_username"] = duser
            t[key] = person
    ROSTER_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return updated
