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


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_score_provenance(message: discord.Message) -> dict[str, Any]:
    """
    Best-effort: when the score was *done* vs when it was posted in the tourney channel.

    score_achieved_at = earliest known time tied to the score content:
      - embed.timestamp (game / bot score time when present)
      - message_snapshots[].created_at (original message time on a Discord forward)
      - reference.resolved.created_at + its embed timestamps (reply / pin of older score)

    Falls back to message.created_at only when no older provenance exists.
    """
    candidates: list[tuple[str, datetime]] = []

    def _add(label: str, dt: datetime | None) -> None:
        utc = _as_utc(dt)
        if utc is not None:
            candidates.append((label, utc))

    for i, embed in enumerate(message.embeds or []):
        _add(f"embed[{i}].timestamp", getattr(embed, "timestamp", None))

    for i, snap in enumerate(getattr(message, "message_snapshots", None) or []):
        _add(f"snapshot[{i}].created_at", getattr(snap, "created_at", None))
        for j, embed in enumerate(getattr(snap, "embeds", None) or []):
            _add(f"snapshot[{i}].embed[{j}].timestamp", getattr(embed, "timestamp", None))

    ref = getattr(message, "reference", None)
    if ref is not None:
        resolved = getattr(ref, "resolved", None)
        if resolved is not None and not isinstance(resolved, discord.DeletedReferencedMessage):
            _add("reference.created_at", getattr(resolved, "created_at", None))
            for j, embed in enumerate(getattr(resolved, "embeds", None) or []):
                _add(f"reference.embed[{j}].timestamp", getattr(embed, "timestamp", None))

    submitted = _as_utc(getattr(message, "created_at", None)) or datetime.now(timezone.utc)
    if not candidates:
        return {
            "submitted_at": submitted,
            "score_achieved_at": submitted,
            "score_source": "message.created_at",
            "evidence": [],
        }

    best_src, best_dt = min(candidates, key=lambda x: x[1])
    return {
        "submitted_at": submitted,
        "score_achieved_at": best_dt,
        "score_source": best_src,
        "evidence": [(src, dt.isoformat()) for src, dt in sorted(candidates, key=lambda x: x[1])],
    }


def submission_timing(
    state: dict[str, Any],
    *,
    week: int | None = None,
    submitted_at: datetime | None = None,
) -> str:
    """
    Where the Discord submit falls relative to the event window.

    Returns:
      "before" — week not open yet (scheduled) OR message time before open_at
      "open"   — valid live window
      "after"  — week closed (late)
    """
    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    w = get_week(state, week_n)
    status = (w.get("status") or "scheduled").lower()
    now = submitted_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    if status == "scheduled":
        return "before"
    if status == "closed":
        return "after"
    if status == "open":
        open_at = _parse_iso_utc(w.get("open_at"))
        # Hard rule: submit must not be before the recorded open time
        if open_at is not None and now < open_at:
            return "before"
        close_at = _parse_iso_utc(w.get("close_at"))
        if close_at is not None and now >= close_at:
            return "after"
        return "open"
    return "before"


def score_done_before_open(
    state: dict[str, Any],
    *,
    week: int | None = None,
    score_achieved_at: datetime | None = None,
) -> bool:
    """True if the score itself was achieved before the week's open_at."""
    if score_achieved_at is None:
        return False
    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    open_at = _parse_iso_utc(get_week(state, week_n).get("open_at"))
    if open_at is None:
        return False
    achieved = _as_utc(score_achieved_at)
    if achieved is None:
        return False
    return achieved < open_at


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
    submitted_at: datetime | None = None,
    score_achieved_at: datetime | None = None,
    score_time_source: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """
    Add a score submission for a week (default: season current_week).
    Returns (submission_or_None, status_message).

    Timing (player embeds / non-staff):
      - Discord post **before** event open → **rejected**
      - Score **done** before open_at (embed/forward original time) → **rejected**
      - **open** window + score after open → auto-verified
      - **after** close (score after open) → pending (staff approve)

    Staff verified=True / approved_by still overrides (manual set / approve).
    """
    team = find_team_by_user(state, user_id)
    # Fixed Season 1 roster: also match Smash / display name on the score embed
    if not team and meta:
        try:
            from roster_fixed import find_team_by_smash_or_display

            team = find_team_by_smash_or_display(state, meta.get("playerName"))
        except Exception:
            team = None
    if not team:
        return None, (
            "Could not match this score to a Season 1 team "
            "(Discord account or Smash name on the embed)."
        )

    week_n = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    if week_n < 1:
        week_n = 1

    submit_ts = _as_utc(submitted_at) or datetime.now(timezone.utc)
    achieved_ts = _as_utc(score_achieved_at) or submit_ts

    timing = submission_timing(state, week=week_n, submitted_at=submit_ts)
    staff_override = verified is True or approved_by is not None
    pre_event_score = score_done_before_open(
        state, week=week_n, score_achieved_at=achieved_ts
    )

    # Hard reject: Discord post before the event window starts
    if not staff_override and timing == "before":
        return None, (
            f"**Rejected** — this score was submitted **before** week {week_n} opened. "
            f"Wait until the event is live, then send a score from the open window."
        )

    # Hard reject: score itself was *done* before open (even if posted after open)
    if not staff_override and pre_event_score:
        open_at = _parse_iso_utc(get_week(state, week_n).get("open_at"))
        open_s = open_at.strftime("%Y-%m-%d %H:%M UTC") if open_at else "week open"
        done_s = achieved_ts.strftime("%Y-%m-%d %H:%M UTC")
        return None, (
            f"**Rejected** — this score was **done before** week {week_n} started "
            f"(`{done_s}` is before open `{open_s}`). "
            f"Only runs from the event window count. Play again after open and re-submit."
        )

    # Explicit verified=True (staff manual / approve path) always wins.
    if verified is True:
        pass
    elif force_pending:
        verified = False
    elif verified is None:
        if timing == "open":
            verified = True
        elif approved_by is not None:
            verified = True
        else:
            # after close → pending
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
        "meta": {
            **(meta or {}),
            "timing": timing if not staff_override else "staff_override",
            "submitted_at": submit_ts.isoformat(),
            "score_achieved_at": achieved_ts.isoformat(),
            "score_time_source": score_time_source or "submitted_at",
        },
        "created_at": submit_ts.isoformat(),
        "approved_by": str(approved_by) if approved_by else None,
    }
    state.setdefault("submissions", []).append(sub)
    if persist:
        save_state(state)

    if sub["verified"]:
        return sub, f"Verified **{score:,}** for week {week_n} (best verified counts)."
    return sub, (
        f"Recorded **{score:,}** as **pending** (submitted after week close). "
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
