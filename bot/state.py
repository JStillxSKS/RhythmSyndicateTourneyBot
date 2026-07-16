"""Persistent season state (JSON on disk)."""
from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from config import DIVISIONS, SEASON_WEEKS, STATE_PATH

# Serialize disk writes (flood / multi-command safety in one process)
_state_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_week(n: int) -> dict[str, Any]:
    return {
        "number": n,
        "song_title": None,
        "song_artist": None,
        "difficulty": None,
        "status": "scheduled",  # scheduled | open | closed
        "open_at": None,
        "close_at": None,
    }


def empty_state() -> dict[str, Any]:
    return {
        "season": {
            "id": "season-1",
            "name": "Season 1",
            "current_week": 1,
            "timezone": "America/Los_Angeles",
        },
        "weeks": {str(i): empty_week(i) for i in range(1, SEASON_WEEKS + 1)},
        "teams": [],
        "submissions": [],
        "dashboard_message_id": None,
        "standings_message_id": None,
        "updated_at": None,
    }


def _merge_shape(data: dict[str, Any]) -> dict[str, Any]:
    base = empty_state()
    if not isinstance(data, dict):
        return base
    base.update({k: v for k, v in data.items() if k in base or k in data})
    # season
    season = base.get("season") or {}
    if not isinstance(season, dict):
        season = {}
    s0 = empty_state()["season"]
    s0.update(season)
    base["season"] = s0
    # weeks
    weeks_in = data.get("weeks") if isinstance(data.get("weeks"), dict) else {}
    weeks: dict[str, Any] = {}
    for i in range(1, SEASON_WEEKS + 1):
        key = str(i)
        w = empty_week(i)
        raw = weeks_in.get(key) or weeks_in.get(i)  # type: ignore[arg-type]
        if isinstance(raw, dict):
            w.update(raw)
            w["number"] = i
        weeks[key] = w
    base["weeks"] = weeks
    if not isinstance(base.get("teams"), list):
        base["teams"] = []
    if not isinstance(base.get("submissions"), list):
        base["submissions"] = []
    return base


def load_state() -> dict[str, Any]:
    with _state_lock:
        if not STATE_PATH.is_file():
            return empty_state()
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return _merge_shape(data if isinstance(data, dict) else {})
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARNING: could not read state: {e}")
            return empty_state()


def save_state(state: dict[str, Any]) -> None:
    """Atomic write with lock + rolling .bak.json."""
    with _state_lock:
        payload = deepcopy(state)
        payload["updated_at"] = _now_iso()
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Rolling backup of previous file (helps Render / fat-finger recovery)
            if STATE_PATH.is_file():
                bak = STATE_PATH.with_suffix(".bak.json")
                try:
                    bak.write_bytes(STATE_PATH.read_bytes())
                except OSError:
                    pass
            tmp = STATE_PATH.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp.replace(STATE_PATH)
            # Mirror updated_at onto caller's dict so in-memory stays consistent
            state["updated_at"] = payload["updated_at"]
        except OSError as e:
            print(f"Could not save state: {e}")


def new_team_id() -> str:
    return f"team-{uuid.uuid4().hex[:10]}"


def new_submission_id() -> str:
    return f"sub-{uuid.uuid4().hex[:12]}"


def find_team_by_user(state: dict[str, Any], user_id: int | str) -> dict[str, Any] | None:
    uid = str(user_id)
    for t in state.get("teams") or []:
        if not t.get("active", True):
            continue
        if str(t.get("captain_user_id")) == uid or str(t.get("teammate_user_id")) == uid:
            return t
    return None


def find_team_by_id(state: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    for t in state.get("teams") or []:
        if t.get("id") == team_id:
            return t
    return None


def find_team_by_name(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    key = (name or "").strip().lower()
    for t in state.get("teams") or []:
        if (t.get("name") or "").strip().lower() == key:
            return t
    return None


def get_week(state: dict[str, Any], week: int | None = None) -> dict[str, Any]:
    if week is None:
        week = int(state.get("season", {}).get("current_week") or 1)
    return state["weeks"][str(int(week))]


def normalize_division(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if key in DIVISIONS:
        return key
    return None
