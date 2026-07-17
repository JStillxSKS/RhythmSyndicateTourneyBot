"""Player slash commands: /tourney …"""
from __future__ import annotations

from typing import Callable

import discord
from discord import app_commands

from config import DIVISIONS
from dashboard import (
    build_dashboard_embed,
    build_help_embed,
    build_rules_embed,
    build_score_embed,
    build_standings_embeds,
    build_team_embed,
    logo_file,
)
from state import find_team_by_user

GetState = Callable[[], dict]
SaveState = Callable[[dict], None]


def register_player_commands(
    tree: app_commands.CommandTree,
    get_state: GetState,
    save_state: SaveState,
) -> None:
    tourney = app_commands.Group(name="tourney", description="Rhythm Syndicate tournament (players)")

    @tourney.command(name="status", description="Current week, song, deadline")
    async def status(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        embed = build_dashboard_embed(state, with_image=True)
        files: list = []
        try:
            from render_boards import board_discord_file, render_ops_from_state
            from theme import DASH_STRIP_NAME, files_for_embeds

            png = render_ops_from_state(state)
            files = files_for_embeds(board_discord_file(png, DASH_STRIP_NAME))
        except Exception:
            lf = logo_file()
            if lf:
                files = [lf]
        if files:
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @tourney.command(name="my-team", description="Your team, division, captain/teammate")
    async def my_team(interaction: discord.Interaction) -> None:
        state = get_state()
        team = find_team_by_user(state, interaction.user.id)
        if not team:
            await interaction.response.send_message(
                "You are not on a registered team. Staff imports teams after registration.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        embed = build_team_embed(state, team, with_image=True)
        files: list = []
        try:
            from rules import team_season_total, team_week_breakdown
            from render_boards import board_discord_file, render_team_card
            from theme import TEAM_CARD_NAME, files_for_embeds

            week_n = int(state.get("season", {}).get("current_week") or 1)
            subs = state.get("submissions") or []
            bd = team_week_breakdown(
                subs, team.get("captain_user_id"), team.get("teammate_user_id"), week_n
            )
            season_tot = team_season_total(
                subs, team.get("captain_user_id"), team.get("teammate_user_id"), through_week=week_n
            )
            png = render_team_card(
                name=team.get("name") or "Team",
                division=team.get("division") or "",
                captain_score=int(bd["captain_score"]),
                teammate_score=int(bd["teammate_score"]),
                team_total=int(bd["team_total"]),
                week=week_n,
                burden=bool(bd["captain_burden"]),
                season_total=season_tot,
            )
            files = files_for_embeds(board_discord_file(png, TEAM_CARD_NAME))
        except Exception:
            lf = logo_file()
            if lf:
                files = [lf]
        if files:
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @tourney.command(name="my-score", description="Your best score this week + team total")
    async def my_score(interaction: discord.Interaction) -> None:
        state = get_state()
        team = find_team_by_user(state, interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not on a registered team.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        embed = build_score_embed(state, team, interaction.user.id, with_image=True)
        files: list = []
        try:
            from rules import player_week_score
            from render_boards import board_discord_file, render_score_flash
            from theme import SCORE_FLASH_NAME, files_for_embeds

            week_n = int(state.get("season", {}).get("current_week") or 1)
            mine = player_week_score(state.get("submissions") or [], interaction.user.id, week_n)
            png = render_score_flash(
                score=mine,
                verified=True,
                week=week_n,
                player=interaction.user.display_name,
                team=team.get("name"),
            )
            files = files_for_embeds(board_discord_file(png, SCORE_FLASH_NAME))
        except Exception:
            lf = logo_file()
            if lf:
                files = [lf]
        if files:
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @tourney.command(name="standings", description="Division standings")
    @app_commands.describe(division="classic | fusion | arcade (omit for all)")
    async def standings(interaction: discord.Interaction, division: str | None = None) -> None:
        div = None
        if division:
            div = division.strip().lower()
            if div not in DIVISIONS:
                await interaction.response.send_message(
                    f"Unknown division. Use: {', '.join(DIVISIONS)}",
                    ephemeral=True,
                )
                return
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        embeds = build_standings_embeds(state, div, with_image=True)
        files: list = []
        try:
            from render_boards import board_discord_file, render_standings_from_state
            from theme import STANDINGS_ATTACHMENT_NAME, files_for_embeds

            png = render_standings_from_state(state, div)
            files = files_for_embeds(board_discord_file(png, STANDINGS_ATTACHMENT_NAME))
        except Exception:
            lf = logo_file()
            if lf:
                files = [lf]
        if files:
            await interaction.followup.send(embeds=embeds[:4], files=files, ephemeral=True)
        else:
            await interaction.followup.send(embeds=embeds[:4], ephemeral=True)

    @tourney.command(name="rules", description="Season 1 rules")
    async def rules_cmd(interaction: discord.Interaction) -> None:
        embed = build_rules_embed()
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tourney.command(name="help", description="Player commands + bot build")
    async def help_cmd(interaction: discord.Interaction) -> None:
        embed = build_help_embed()
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(tourney)
