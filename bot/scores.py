"""Score embed parse + submission pipeline."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import discord

from state import find_team_by_user, get_week, new_submission_id, save_state

GAME_MODE_MAP = {
    "classic": "classic",
    "arcade": "arcade",
    "fusion": "fusion",
}
DIFFICULTY_MAP = {
    "easy": "easy",
    "normal": "normal",
    "hard": "hard",
    "extreme": "extreme",
    "hardcore": "hardcore",
}


def normalize_difficulty(raw: str) -> str:
    key = (raw or "").lower().strip()
    return DIFFICULTY_MAP.get(key, key if key in DIFFICULTY_MAP.values() else "normal")


def normalize_game_mode(raw: str) -> str | None:
    key = (raw or "").lower().strip()
    if key in GAME_MODE_MAP:
        return GAME_MODE_MAP[key]
    return None


def parse_player_name(name: str | None) -> str:
    if not name:
        return "Unknown"
    return re.sub(r"\s*\([^)]+\)\s*$", "", name).strip() or "Unknown"


def is_game_footer(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("smash drums") or ("quest" in t and bool(re.search(r"\d+\.\d+", t)))


def parse_embed(embed: discord.Embed) -> dict[str, Any] | None:
    if not embed:
        return None

    data: dict[str, Any] = {"artist": "", "title": ""}
    desc = embed.description or ""
    fields = {f.name.lower(): f.value for f in (embed.fields or [])}

    song_val = fields.get("song", "")
    indie_match = re.match(r"\[Indies\]\s*(\S+)", song_val, re.I)
    if indie_match:
        data["inGameSongId"] = indie_match.group(1)
        data["isIndie"] = True
        data["title"] = song_val.strip()
    elif song_val:
        data["title"] = song_val.strip()
    elif embed.title and "⭐" not in embed.title and "★" not in embed.title:
        data["title"] = embed.title.strip()

    score = 0
    for key in ("score", "points"):
        if key in fields:
            score = int(re.sub(r"[^\d]", "", fields[key]) or 0)
            break
    if not score and desc:
        m = re.search(r"([\d,]+)", desc)
        if m:
            score = int(re.sub(r"[^\d]", "", m.group(1)) or 0)
    data["score"] = score

    raw_diff = fields.get("difficulty") or fields.get("diff") or ""
    data["difficultyRaw"] = raw_diff.strip()
    data["difficulty"] = normalize_difficulty(raw_diff)

    raw_mode = fields.get("game mode") or fields.get("gamemode") or fields.get("mode") or ""
    data["gameModeRaw"] = raw_mode.strip()
    data["gameMode"] = normalize_game_mode(raw_mode)

    artist_match = re.search(r"Artist[:\s]+(.+?)(?:\n|$)", desc, re.I)
    if artist_match:
        data["artist"] = artist_match.group(1).strip()

    if embed.author and embed.author.name:
        data["playerName"] = parse_player_name(embed.author.name)
    elif embed.footer and embed.footer.text and not is_game_footer(embed.footer.text):
        data["playerName"] = parse_player_name(embed.footer.text)
    else:
        data["playerName"] = "Unknown"

    if data.get("score") or data.get("title") or data.get("inGameSongId"):
        return data
    return None


def iter_message_embeds(message: discord.Message):
    for embed in message.embeds or []:
        yield embed
    for snap in getattr(message, "message_snapshots", None) or []:
        for embed in getattr(snap, "embeds", None) or []:
            yield embed


def parse_game_score_message(message: discord.Message) -> dict[str, Any] | None:
    for embed in iter_message_embeds(message):
        data = parse_embed(embed)
        if data and data.get("score"):
            return data
    return None


def week_is_open(state: dict[str, Any], week: int | None = None) -> bool:
    w = get_week(state, week)
    return (w.get("status") or "") == "open"


def find_submission_by_message_id(
    state: dict[str, Any], message_id: int | str | None
) -> dict[str, Any] | None:
    """Return first submission with this Discord message id (if any)."""
    if message_id is None:
        return None
    mid = str(message_id)
    for s in state.get("submissions") or []:
        if s.get("message_id") is not None and str(s.get("message_id")) == mid:
            return s
    return None


def record_submission(
    state: dict[str, Any],
    *,
    user_id: int,
    score: int,
    source: str = "embed",
    message_id: int | None = None,
    channel_id: int | None = None,
    meta: dict[str, Any] | None = None,
    force_pending: bool = False,
    verified: bool | None = None,
    approved_by: int | None = None,
    persist: bool = True,
    week: int | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """
    Add a score submission for a week (default: season current_week).
    Returns (submission_or_None, status_message).

    - Same Discord message_id is not recorded twice (re-forward / double-fire).
    - persist=False skips disk write (playground flood / batch tests).
    - week= targets a specific week without mutating season.current_week
      (critical for /rs score set on past weeks during an open window).
    """
    team = find_team_by_user(state, user_id)
    if not team:
        return None, "You are not on a registered tournament team."

    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    if week_n < 1:
        week_n = 1
    open_now = week_is_open(state, week_n)

    # Explicit verified=True (staff manual / approve path) always wins.
    if verified is True:
        pass
    elif force_pending:
        verified = False
    elif verified is None:
        # On-time auto-verify; closed week → pending unless staff approved_by
        if open_now:
            verified = True
        elif approved_by is not None:
            verified = True
        else:
            verified = False
    # verified is False stays False

    score = int(score or 0)
    if score <= 0:
        return None, "Score must be greater than zero."

    # Idempotent: one Discord message → one submission row
    if message_id is not None:
        existing = find_submission_by_message_id(state, message_id)
        if existing is not None:
            return existing, (
                f"Already recorded from this message "
                f"(**{int(existing.get('score') or 0):,}**, "
                f"{'verified' if existing.get('verified') else 'pending'})."
            )

    sub = {
        "id": new_submission_id(),
        "team_id": team["id"],
        "user_id": str(user_id),
        "week": week_n,
        "score": score,
        "verified": bool(verified),
        "source": source,
        "message_id": str(message_id) if message_id else None,
        "channel_id": str(channel_id) if channel_id else None,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": str(approved_by) if approved_by else None,
    }
    state.setdefault("submissions", []).append(sub)
    if persist:
        save_state(state)

    if sub["verified"]:
        return sub, f"Verified **{score:,}** for week {week_n} (best verified counts)."
    return sub, (
        f"Recorded **{score:,}** as **pending** (week closed or needs approval). "
        f"Staff: `/rs submission approve`."
    )


def approve_submission(
    state: dict[str, Any],
    submission_id: str,
    admin_id: int,
    *,
    persist: bool = True,
) -> tuple[dict | None, str]:
    for s in state.get("submissions") or []:
        if s.get("id") == submission_id:
            s["verified"] = True
            s["approved_by"] = str(admin_id)
            if persist:
                save_state(state)
            return s, f"Approved `{submission_id}` — score **{int(s.get('score') or 0):,}** now counts."
    return None, f"No submission `{submission_id}`."


def pending_for_user(state: dict[str, Any], user_id: int, week: int | None = None) -> list[dict]:
    uid = str(user_id)
    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    return [
        s
        for s in state.get("submissions") or []
        if str(s.get("user_id")) == uid
        and int(s.get("week") or 0) == week_n
        and not s.get("verified")
    ]


def list_pending(state: dict[str, Any], week: int | None = None, limit: int = 15) -> list[dict]:
    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    pending = [
        s
        for s in state.get("submissions") or []
        if int(s.get("week") or 0) == week_n and not s.get("verified")
    ]
    pending.sort(key=lambda s: s.get("created_at") or "")
    return pending[-limit:]
