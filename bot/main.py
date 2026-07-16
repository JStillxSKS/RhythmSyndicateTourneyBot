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
from scores import parse_game_score_message, record_submission
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

    state = get_state()
    from state import find_team_by_user

    team = find_team_by_user(state, message.author.id)
    mode = data.get("gameMode")
    mode_note = ""
    if team and mode and team.get("division") and mode != team.get("division"):
        mode_note = (
            f"\n⚠️ Embed mode **{mode}** ≠ team division **{team.get('division')}** "
            "(score still counted; staff can review)."
        )

    sub, status = record_submission(
        state,
        user_id=message.author.id,
        score=int(data.get("score") or 0),
        source="embed",
        message_id=message.id,
        channel_id=message.channel.id,
        meta={
            "title": data.get("title"),
            "artist": data.get("artist"),
            "gameMode": data.get("gameMode"),
            "difficulty": data.get("difficulty"),
            "playerName": data.get("playerName"),
            "team_division": team.get("division") if team else None,
        },
    )
    from dashboard import build_submission_reply_embed, logo_file

    status = status + mode_note

    if sub is None:
        try:
            await message.add_reaction("❓")
            embed = build_submission_reply_embed(
                verified=False,
                status_text=status,
                score=int(data.get("score") or 0) or None,
            )
            file = logo_file()
            if file:
                await message.reply(embed=embed, file=file, mention_author=False)
            else:
                await message.reply(embed=embed, mention_author=False)
        except discord.HTTPException:
            pass
        return

    try:
        await message.add_reaction("✅" if sub.get("verified") else "⏳")
        embed = build_submission_reply_embed(
            verified=bool(sub.get("verified")),
            status_text=status,
            score=int(sub.get("score") or 0),
            week=int(sub.get("week") or 0) or None,
        )
        file = logo_file()
        if file:
            await message.reply(embed=embed, file=file, mention_author=False)
        else:
            await message.reply(embed=embed, mention_author=False)
    except discord.HTTPException:
        pass


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
