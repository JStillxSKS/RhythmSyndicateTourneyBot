"""
Week open/close + public board refresh — shared by slash commands and automation.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

import discord

from config import (
    CAPTAIN_BURDEN_WEEK,
    RS_BOARD_THROTTLE_SEC,
    RS_CHANNEL_ID,
    SEASON_WEEKS,
)
from dashboard import build_dashboard_embed, build_standings_embeds
from deadline import default_week_close_utc
from state import get_week, save_state

GetState = Callable[[], dict]
SaveState = Callable[[dict], None]

# process-local throttle for board edits
_last_board_refresh_mono: float = 0.0


def open_week(
    state: dict[str, Any],
    week_n: int | None = None,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    """Mark week open; set open_at / default close_at. Returns (week_dict, week_n)."""
    now = now or datetime.now(timezone.utc)
    week_n = int(week_n or state.get("season", {}).get("current_week") or 1)
    week_n = max(1, min(week_n, SEASON_WEEKS))
    state.setdefault("season", {})["current_week"] = week_n
    w = get_week(state, week_n)
    w["status"] = "open"
    w["open_at"] = now.isoformat()
    if not w.get("close_at"):
        w["close_at"] = default_week_close_utc(now).isoformat()
    auto = state.setdefault("auto", {})
    auto["last_open_at"] = now.isoformat()
    auto["last_open_week"] = week_n
    save_state(state)
    return w, week_n


def close_week(
    state: dict[str, Any],
    week_n: int | None = None,
    *,
    now: datetime | None = None,
    advance: bool = False,
) -> tuple[dict[str, Any], int]:
    """Mark week closed. Set advance=True only after public close announce."""
    now = now or datetime.now(timezone.utc)
    week_n = int(week_n or state.get("season", {}).get("current_week") or 1)
    week_n = max(1, min(week_n, SEASON_WEEKS))
    w = get_week(state, week_n)
    w["status"] = "closed"
    w["close_at"] = now.isoformat()
    auto = state.setdefault("auto", {})
    auto["last_close_at"] = now.isoformat()
    auto["last_close_week"] = week_n
    if advance:
        advance_to_next_week(state, from_week=week_n)
    save_state(state)
    return w, week_n


def advance_to_next_week(state: dict[str, Any], *, from_week: int | None = None) -> int | None:
    """After a close: move current_week forward if possible. Returns new week or None."""
    week_n = int(from_week or state.get("season", {}).get("current_week") or 1)
    if week_n >= SEASON_WEEKS:
        return None
    nxt = week_n + 1
    state.setdefault("season", {})["current_week"] = nxt
    nw = get_week(state, nxt)
    if (nw.get("status") or "") != "open":
        nw["status"] = "scheduled"
    save_state(state)
    return nxt


async def resolve_tourney_channel(bot: discord.Client) -> discord.TextChannel | discord.Thread | None:
    if not RS_CHANNEL_ID:
        return None
    ch = bot.get_channel(RS_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(RS_CHANNEL_ID)
        except discord.HTTPException:
            return None
    if isinstance(ch, (discord.TextChannel, discord.Thread)):
        return ch
    return None


async def post_week_announce(
    bot: discord.Client,
    state: dict[str, Any],
    *,
    style: str,
) -> None:
    """Public week open/close announce (reuses admin announce pipeline)."""
    channel = await resolve_tourney_channel(bot)
    if not channel:
        print("AUTO announce skipped: no RS_CHANNEL_ID / channel")
        return
    # Import here to avoid circular import at module load
    from commands_admin import _post_week_announce

    await _post_week_announce(channel, state, style=style)


async def refresh_public_boards(
    bot: discord.Client,
    state: dict[str, Any],
    *,
    force: bool = False,
) -> str:
    """Edit living dashboard + standings messages. Throttled unless force."""
    global _last_board_refresh_mono
    now_m = time.monotonic()
    if not force and (now_m - _last_board_refresh_mono) < RS_BOARD_THROTTLE_SEC:
        return "throttled"
    channel = await resolve_tourney_channel(bot)
    if not channel:
        return "no_channel"

    notes: list[str] = []

    # Dashboard
    dash_id = state.get("dashboard_message_id")
    if dash_id:
        try:
            from commands_admin import _dashboard_files

            embed = build_dashboard_embed(state, with_image=True)
            msg = await channel.fetch_message(int(dash_id))
            files = _dashboard_files(state)
            await msg.edit(embed=embed, attachments=files or [])
            notes.append("dashboard")
        except Exception as e:
            print(f"Dashboard refresh failed: {e}")
            notes.append("dashboard_fail")

    # Standings
    stand_id = state.get("standings_message_id")
    if stand_id:
        try:
            from commands_admin import _standings_files

            embeds = build_standings_embeds(state, with_image=True)
            msg = await channel.fetch_message(int(stand_id))
            files = _standings_files(state)
            await msg.edit(content=None, embeds=embeds, attachments=files or [])
            notes.append("standings")
        except Exception as e:
            print(f"Standings refresh failed: {e}")
            notes.append("standings_fail")

    if notes:
        _last_board_refresh_mono = now_m
        state.setdefault("auto", {})["last_board_refresh"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
    return ",".join(notes) if notes else "no_messages"


def season_status_text(state: dict[str, Any], *, auto_week: bool) -> str:
    from config import BOT_VERSION, RS_AUTO_DIGEST, RS_TEST_TIME, RS_TZ
    from timeclock import format_clock_status

    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    w = get_week(state, week_n)
    song = w.get("song_title") or "*(not set)*"
    if w.get("song_artist"):
        song = f"{song} — {w['song_artist']}"
    lines = [
        f"**Build:** `{BOT_VERSION}`",
        f"**Auto week clock:** {'ON' if auto_week else 'OFF'}",
        f"**Missing digest:** {'ON' if RS_AUTO_DIGEST else 'OFF'}",
        f"**Test time:** {'ON' if RS_TEST_TIME else 'OFF'}",
        format_clock_status(state),
        f"**Current week:** **{week_n}** / {SEASON_WEEKS} · status **{w.get('status')}**",
        f"**Song:** {song}",
        f"**Captain's Burden:** {'ACTIVE' if week_n == CAPTAIN_BURDEN_WEEK else f'week {CAPTAIN_BURDEN_WEEK}'}",
        f"**Teams:** {len([t for t in state.get('teams') or [] if t.get('active', True)])}",
        f"**Timezone:** {RS_TZ}",
    ]
    auto = state.get("auto") or {}
    if auto.get("last_open_at"):
        lines.append(f"**Last auto open:** week {auto.get('last_open_week')} · `{auto.get('last_open_at')}`")
    if auto.get("last_close_at"):
        lines.append(f"**Last auto close:** week {auto.get('last_close_week')} · `{auto.get('last_close_at')}`")
    # Song queue peek
    lines.append("**Song queue:**")
    for i in range(1, SEASON_WEEKS + 1):
        wi = get_week(state, i)
        t = wi.get("song_title") or "—"
        lines.append(f"· W{i} ({wi.get('status')}): {t}")
    return "\n".join(lines)
