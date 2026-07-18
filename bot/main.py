#!/usr/bin/env python3
"""
Rhythm Syndicate Tournament Bot — Season 1 foundation.

Players: /tourney …
Staff:   /rs …
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow `python bot/main.py` and `python -m bot.main` from project root
BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import discord
from aiohttp import web
from discord import app_commands

from commands_admin import register_admin_commands
from commands_player import register_player_commands
from config import (
    BOT_VERSION,
    DISCORD_TOKEN,
    RS_CHANNEL_ID,
    RS_GUILD_ID,
    RS_SUBMIT_CHANNEL_ID,
)
from scores import extract_score_provenance, parse_game_score_message, record_submission
from state import load_state, save_state

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

_state = load_state()


def get_state() -> dict:
    return _state


def set_and_save(state: dict) -> None:
    global _state
    _state = state
    save_state(_state)


def refresh_state() -> dict:
    """Reload from disk (optional); normally mutate _state in place."""
    global _state
    _state = load_state()
    return _state


# ---------------------------------------------------------------------------
# Discord client
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
# Members intent not required for role checks on interaction.user in guilds

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready() -> None:
    print(f"RS TOURNEY BOT ONLINE BOT_VERSION={BOT_VERSION} user={client.user}")
    if RS_CHANNEL_ID:
        print(f"Watching channel id={RS_CHANNEL_ID} (submit={RS_SUBMIT_CHANNEL_ID})")
    else:
        print("WARNING: RS_CHANNEL_ID not set")

    try:
        if RS_GUILD_ID:
            guild = discord.Object(id=RS_GUILD_ID)
            tree.copy_global_to(guild=guild)
            synced = await tree.sync(guild=guild)
            print(f"Synced {len(synced)} guild commands to {RS_GUILD_ID}")
        else:
            synced = await tree.sync()
            print(f"Synced {len(synced)} global commands (set RS_GUILD_ID for faster guild sync)")
    except Exception as e:
        print(f"Command sync failed: {e}")

    # Automation: heal missed open/close if bot was offline
    try:
        from scheduler import catch_up_once

        await catch_up_once(client, get_state)
    except Exception as e:
        print(f"AUTO catch-up failed: {e}")

    # Start season clock once
    if not getattr(client, "_rs_scheduler_started", False):
        client._rs_scheduler_started = True  # type: ignore[attr-defined]
        from scheduler import scheduler_loop

        client.loop.create_task(scheduler_loop(client, get_state))


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return
    # Only tourney / submit channel
    watch = {c for c in (RS_CHANNEL_ID, RS_SUBMIT_CHANNEL_ID) if c}
    if watch and message.channel.id not in watch:
        return

    data = parse_game_score_message(message)
    if not data:
        return

    # Try to resolve reply/forward originals so we can see when the score was *done*
    try:
        ref = getattr(message, "reference", None)
        if (
            ref is not None
            and getattr(ref, "resolved", None) is None
            and getattr(ref, "message_id", None)
            and getattr(ref, "channel_id", None)
        ):
            try:
                ch = message.channel
                if getattr(ch, "id", None) != ref.channel_id:
                    ch = client.get_channel(ref.channel_id) or await client.fetch_channel(
                        ref.channel_id
                    )
                if ch is not None and hasattr(ch, "fetch_message"):
                    ref.resolved = await ch.fetch_message(ref.message_id)  # type: ignore[attr-defined]
            except Exception:
                pass

        provenance = extract_score_provenance(message)
    except Exception:
        from datetime import timezone as _tz

        submitted_at = message.created_at
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=_tz.utc)
        provenance = {
            "submitted_at": submitted_at,
            "score_achieved_at": submitted_at,
            "score_source": "message.created_at",
            "evidence": [],
        }

    state = get_state()
    from state import find_team_by_user

    team = find_team_by_user(state, message.author.id)
    if not team:
        try:
            from roster_fixed import find_team_by_smash_or_display

            team = find_team_by_smash_or_display(state, data.get("playerName"))
        except Exception:
            pass
    mode = data.get("gameMode")
    mode_note = ""
    if team and mode and team.get("division") and mode != team.get("division"):
        mode_note = (
            f"\n⚠️ Embed mode **{mode}** ≠ team division **{team.get('division')}** "
            "(score still counted; staff can review)."
        )

    submitted_at = provenance["submitted_at"]
    score_achieved_at = provenance["score_achieved_at"]
    score_source = provenance.get("score_source") or "message.created_at"

    meta = {
        "title": data.get("title"),
        "artist": data.get("artist"),
        "gameMode": data.get("gameMode"),
        "difficulty": data.get("difficulty"),
        "playerName": data.get("playerName"),
        "team_division": team.get("division") if team else None,
        "score_time_evidence": provenance.get("evidence") or [],
    }
    sub, status = record_submission(
        state,
        user_id=message.author.id,
        score=int(data.get("score") or 0),
        source="embed",
        message_id=message.id,
        channel_id=message.channel.id,
        submitted_at=submitted_at,
        score_achieved_at=score_achieved_at,
        score_time_source=str(score_source),
        meta=meta,
    )
    from dashboard import build_submission_reply_embed, logo_file
    from theme import SCORE_FLASH_NAME, files_for_embeds

    rejected_before = (
        sub is None
        and "Rejected" in (status or "")
        and (
            "before" in (status or "").lower()
            or "done before" in (status or "").lower()
        )
    )
    status = status + mode_note
    verified = bool(sub and sub.get("verified"))
    score_val = int((sub or {}).get("score") or data.get("score") or 0)
    week_val = int((sub or {}).get("week") or state.get("season", {}).get("current_week") or 0) or None

    if sub is None:
        try:
            await message.add_reaction("❌" if rejected_before else "❓")
        except discord.HTTPException:
            pass
        verified = False
    else:
        try:
            await message.add_reaction("✅" if verified else "⏳")
        except discord.HTTPException:
            pass

    try:
        embed = build_submission_reply_embed(
            verified=verified if sub is not None else False,
            status_text=status,
            score=score_val or None,
            week=week_val,
        )
        files: list = []
        try:
            from render_boards import board_discord_file, render_score_flash

            png = render_score_flash(
                score=score_val or 0,
                verified=bool(sub and sub.get("verified")),
                week=int(week_val or 1),
                player=(data.get("playerName") or message.author.display_name),
                team=(team.get("name") if team else None),
                mode_note="Mode ≠ division — staff may review" if mode_note else None,
            )
            embed.set_image(url=f"attachment://{SCORE_FLASH_NAME}")
            files = files_for_embeds(board_discord_file(png, SCORE_FLASH_NAME))
        except Exception as e:
            print(f"Score flash render failed: {e}")
            lf = logo_file()
            if lf:
                files = [lf]
        if files:
            await message.reply(embed=embed, files=files, mention_author=False)
        else:
            await message.reply(embed=embed, mention_author=False)
    except discord.HTTPException:
        pass

    # Auto-refresh public boards after a verified score (throttled)
    if sub and sub.get("verified"):
        try:
            from lifecycle import refresh_public_boards

            note = await refresh_public_boards(client, get_state(), force=False)
            if note not in ("throttled", "no_channel", "no_messages"):
                print(f"AUTO board refresh after score: {note}")
        except Exception as e:
            print(f"AUTO board refresh failed: {e}")


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    msg = "Command failed."
    if isinstance(error, app_commands.CheckFailure):
        msg = str(error) or "You cannot use this command."
    else:
        print(f"Command error: {error}")
        msg = f"Error: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# Register command groups
register_player_commands(tree, get_state, set_and_save)
register_admin_commands(tree, get_state, set_and_save, client)


# ---------------------------------------------------------------------------
# Health server (Render web service free tier)
# ---------------------------------------------------------------------------

async def health(_request: web.Request) -> web.Response:
    return web.Response(text=f"ok {BOT_VERSION}\n")


async def start_health_server() -> web.AppRunner | None:
    port = os.getenv("PORT")
    if not port:
        return None
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(port))
    await site.start()
    print(f"Health server on :{port}/health")
    return runner


async def amain() -> None:
    if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: set DISCORD_TOKEN in environment or .env")
        sys.exit(1)
    await start_health_server()
    await client.start(DISCORD_TOKEN)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("Shutting down")


if __name__ == "__main__":
    main()
