"""
Season clock automation (America/Los_Angeles).

Sat 10:00 → open current week (+ announce + board refresh)
Fri 23:59 → close current week (+ announce + board refresh + advance week)

Catch-up on every tick / on_ready if bot was offline at the boundary.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from config import (
    RS_AUTO_ANNOUNCE,
    RS_AUTO_DIGEST,
    RS_AUTO_WEEK,
    RS_SCHEDULER_TICK_SEC,
    RS_TEST_TIME,
    RS_TZ,
    SEASON_WEEKS,
)
from dashboard import missing_submissions
from lifecycle import (
    advance_to_next_week,
    close_week,
    open_week,
    post_week_announce,
    refresh_public_boards,
)
from state import get_week, save_state
from timeclock import clock_now, ensure_test_origins

if TYPE_CHECKING:
    import discord

GetState = Callable[[], dict]


def in_scoring_window(local: datetime) -> bool:
    """
    True from Saturday 10:00 AM PT through Friday 11:58 PM PT.
    At Friday 23:59 we treat as close.
    """
    wd = local.weekday()  # Mon=0 … Sun=6
    minutes = local.hour * 60 + local.minute
    sat_open = 10 * 60
    fri_close = 23 * 60 + 59
    if wd == 5:  # Saturday
        return minutes >= sat_open
    if wd == 6:  # Sunday
        return True
    if wd in (0, 1, 2, 3):  # Mon–Thu
        return True
    if wd == 4:  # Friday
        return minutes < fri_close
    return False


def evaluate_clock(state: dict[str, Any], *, now: datetime | None = None) -> str | None:
    """
    Pure decision: return 'open', 'close', or None.
    Uses real PT or test-scaled virtual PT (see timeclock).
    """
    if now is None:
        now = clock_now(state)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=RS_TZ)
    else:
        now = now.astimezone(RS_TZ)

    week_n = int(state.get("season", {}).get("current_week") or 1)
    w = get_week(state, week_n)
    status = (w.get("status") or "scheduled").lower()
    window = in_scoring_window(now)

    if window and status in ("scheduled", "closed"):
        # If closed mid-window after a close same week — don't reopen until next Saturday
        # Reopen only if scheduled, OR closed but last close was a previous calendar week
        if status == "scheduled":
            return "open"
        if status == "closed":
            # Only reopen if we're in a new scoring window after advance
            # After close we advance week to scheduled — so closed on current is season-end or same week
            # If still on same week and closed, stay closed until staff opens or next week advanced
            return None
    if (not window) and status == "open":
        return "close"
    return None


async def apply_clock_action(
    bot: discord.Client,
    get_state: GetState,
    action: str,
) -> None:
    state = get_state()
    if action == "open":
        w, week_n = open_week(state)
        print(f"AUTO week open week={week_n} song={w.get('song_title')}")
        if RS_AUTO_ANNOUNCE:
            try:
                await post_week_announce(bot, state, style="week_open")
            except Exception as e:
                print(f"AUTO announce open failed: {e}")
        try:
            await refresh_public_boards(bot, state, force=True)
        except Exception as e:
            print(f"AUTO board refresh open failed: {e}")
    elif action == "close":
        w, week_n = close_week(state, advance=False)
        print(f"AUTO week close week={week_n}")
        if RS_AUTO_ANNOUNCE:
            try:
                await post_week_announce(bot, state, style="week_close")
            except Exception as e:
                print(f"AUTO announce close failed: {e}")
        try:
            await refresh_public_boards(bot, state, force=True)
        except Exception as e:
            print(f"AUTO board refresh close failed: {e}")
        nxt = advance_to_next_week(state, from_week=week_n)
        if nxt:
            print(f"AUTO advanced to week={nxt} (scheduled)")


async def maybe_missing_digest(bot: discord.Client, get_state: GetState) -> None:
    """Wed noon PT-ish: one digest per calendar date if anyone missing."""
    if not RS_AUTO_DIGEST:
        return
    state = get_state()
    local = clock_now(state)
    # Wednesday = 2, after 12:00, before 13:00 window for first tick
    if local.weekday() != 2 or local.hour != 12:
        return
    week_n = int(state.get("season", {}).get("current_week") or 1)
    w = get_week(state, week_n)
    if (w.get("status") or "") != "open":
        return
    today = local.strftime("%Y-%m-%d")
    auto = state.setdefault("auto", {})
    if auto.get("last_missing_digest_date") == today:
        return
    missing = missing_submissions(state, week_n)
    auto["last_missing_digest_date"] = today
    save_state(state)
    if not missing:
        print("AUTO missing digest: none missing")
        return
    from lifecycle import resolve_tourney_channel
    from theme import base_embed, footer_staff, logo_file

    channel = await resolve_tourney_channel(bot)
    if not channel:
        return
    text = "\n".join(missing[:25])
    if len(missing) > 25:
        text += f"\n… +{len(missing) - 25} more"
    embed = base_embed(
        title=f"Mid-week check · Week {week_n}",
        description=f"**{len(missing)}** player(s) still need a verified score:\n\n{text}",
        author="RHYTHM SYNDICATE · AUTO",
    )
    embed.set_footer(text=footer_staff())
    f = logo_file()
    if f:
        await channel.send(embed=embed, file=f)
    else:
        await channel.send(embed=embed)
    print(f"AUTO missing digest posted count={len(missing)}")


async def scheduler_loop(bot: discord.Client, get_state: GetState) -> None:
    await bot.wait_until_ready()
    print(
        f"Scheduler started AUTO_WEEK={RS_AUTO_WEEK} ANNOUNCE={RS_AUTO_ANNOUNCE} "
        f"DIGEST={RS_AUTO_DIGEST} TEST_TIME={RS_TEST_TIME} tick={RS_SCHEDULER_TICK_SEC}s"
    )
    if RS_TEST_TIME:
        st = get_state()
        if not (st.get("auto") or {}).get("test_real_origin_utc"):
            ensure_test_origins(st, anchor="before_open")
            save_state(st)
            print("TEST_TIME: origins set to before_open (virtual Sat 09:50)")
        print(f"TEST_TIME virtual now: {clock_now(st).isoformat()}")
    while not bot.is_closed():
        try:
            if RS_AUTO_WEEK:
                state = get_state()
                action = evaluate_clock(state)
                if action:
                    await apply_clock_action(bot, get_state, action)
            await maybe_missing_digest(bot, get_state)
        except Exception as e:
            print(f"Scheduler tick error: {e}")
        await asyncio.sleep(RS_SCHEDULER_TICK_SEC)


async def catch_up_once(bot: discord.Client, get_state: GetState) -> None:
    """Run immediately on ready so offline boundaries heal."""
    if not RS_AUTO_WEEK:
        print("AUTO week catch-up skipped (RS_AUTO_WEEK off)")
        return
    state = get_state()
    if RS_TEST_TIME and not (state.get("auto") or {}).get("test_real_origin_utc"):
        ensure_test_origins(state, anchor="before_open")
        save_state(state)
    action = evaluate_clock(state)
    if action:
        print(f"AUTO catch-up action={action}")
        await apply_clock_action(bot, get_state, action)
    else:
        v = clock_now(state)
        print(f"AUTO catch-up: no action needed (clock={v.strftime('%a %H:%M %Z')})")
