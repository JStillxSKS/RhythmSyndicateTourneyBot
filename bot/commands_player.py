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
        state = get_state()
        embed = build_dashboard_embed(state)
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

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
        embed = build_team_embed(state, team)
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tourney.command(name="my-score", description="Your best score this week + team total")
    async def my_score(interaction: discord.Interaction) -> None:
        state = get_state()
        team = find_team_by_user(state, interaction.user.id)
        if not team:
            await interaction.response.send_message("You are not on a registered team.", ephemeral=True)
            return
        embed = build_score_embed(state, team, interaction.user.id)
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tourney.command(name="standings", description="Division standings")
    @app_commands.describe(division="classic | fusion | arcade (omit for all)")
    async def standings(interaction: discord.Interaction, division: str | None = None) -> None:
        state = get_state()
        div = None
        if division:
            div = division.strip().lower()
            if div not in DIVISIONS:
                await interaction.response.send_message(
                    f"Unknown division. Use: {', '.join(DIVISIONS)}",
                    ephemeral=True,
                )
                return
        embeds = build_standings_embeds(state, div)
        file = logo_file()
        if file:
            await interaction.response.send_message(
                embeds=embeds[:3], file=file, ephemeral=True
            )
        else:
            await interaction.response.send_message(embeds=embeds[:3], ephemeral=True)

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
