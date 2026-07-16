"""Staff slash commands: /rs …"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import discord
from discord import app_commands

from config import (
    BOT_VERSION,
    DIVISION_LABELS,
    DIVISIONS,
    RS_ADMIN_ROLE_IDS,
    RS_CHANNEL_ID,
    RS_GUILD_ID,
    RS_SUBMIT_CHANNEL_ID,
)
from dashboard import (
    build_admin_ok_embed,
    build_announce_embed,
    build_dashboard_embed,
    build_standings_embeds,
    build_week_status_embed,
    logo_file,
)
from deadline import default_week_close_utc
from render_banners import hero_discord_file, render_hero_from_state
from render_versus import (
    STYLE_LABELS,
    matchup_from_teams,
    render_verse,
    verse_discord_file,
)
from scores import approve_submission, list_pending, record_submission
from state import (
    find_team_by_name,
    find_team_by_user,
    get_week,
    new_team_id,
    normalize_division,
)
from theme import HERO_ATTACHMENT_NAME, VERSE_ATTACHMENT_NAME, files_for_embeds

GetState = Callable[[], dict]
SaveState = Callable[[dict], None]


def is_rs_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    member = interaction.user
    if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
        return True
    if not RS_ADMIN_ROLE_IDS:
        return False
    return any(r.id in RS_ADMIN_ROLE_IDS for r in member.roles)


def admin_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_rs_admin(interaction):
            return True
        raise app_commands.CheckFailure(
            "Staff only. Need Manage Server or an RS admin role (`RS_ADMIN_ROLE_IDS`)."
        )

    return app_commands.check(predicate)


def register_admin_commands(
    tree: app_commands.CommandTree,
    get_state: GetState,
    save_state: SaveState,
    bot: discord.Client,
) -> None:
    rs = app_commands.Group(name="rs", description="Rhythm Syndicate staff commands")

    # --- week ---
    week_grp = app_commands.Group(name="week", description="Open / close the weekly window", parent=rs)

    @week_grp.command(name="open", description="Open the current (or given) week for scores")
    @admin_check()
    @app_commands.describe(
        week="Week number 1–4 (default: current)",
        announce="Also post public announcement in tourney channel (default: on)",
    )
    async def week_open(
        interaction: discord.Interaction,
        week: app_commands.Range[int, 1, 4] | None = None,
        announce: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        week_n = int(week or state.get("season", {}).get("current_week") or 1)
        state["season"]["current_week"] = week_n
        w = get_week(state, week_n)
        now = datetime.now(timezone.utc)
        w["status"] = "open"
        w["open_at"] = now.isoformat()
        if not w.get("close_at"):
            w["close_at"] = default_week_close_utc(now).isoformat()
        save_state(state)

        confirm = build_week_status_embed(state, week_n, opened=True)
        files = files_for_embeds()
        if files:
            await interaction.followup.send(embed=confirm, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=confirm, ephemeral=True)

        if announce:
            channel = await _resolve_channel(bot, interaction)
            if channel:
                await _post_week_announce(channel, state, style="week_open")

    @week_grp.command(name="close", description="Close the current (or given) week")
    @admin_check()
    @app_commands.describe(
        week="Week number 1–4 (default: current)",
        announce="Also post public close notice (default: on)",
    )
    async def week_close(
        interaction: discord.Interaction,
        week: app_commands.Range[int, 1, 4] | None = None,
        announce: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        week_n = int(week or state.get("season", {}).get("current_week") or 1)
        w = get_week(state, week_n)
        w["status"] = "closed"
        if not w.get("close_at"):
            w["close_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state)

        confirm = build_week_status_embed(state, week_n, opened=False)
        files = files_for_embeds()
        if files:
            await interaction.followup.send(embed=confirm, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=confirm, ephemeral=True)

        if announce:
            channel = await _resolve_channel(bot, interaction)
            if channel:
                await _post_week_announce(channel, state, style="week_close")

    # --- song ---
    song_grp = app_commands.Group(name="song", description="Set featured song", parent=rs)

    @song_grp.command(name="set", description="Set the featured song for a week")
    @admin_check()
    @app_commands.describe(
        title="Song title",
        artist="Artist (optional)",
        difficulty="Difficulty label (optional)",
        week="Week 1–4 (default: current)",
    )
    async def song_set(
        interaction: discord.Interaction,
        title: str,
        artist: str | None = None,
        difficulty: str | None = None,
        week: app_commands.Range[int, 1, 4] | None = None,
    ) -> None:
        state = get_state()
        week_n = int(week or state.get("season", {}).get("current_week") or 1)
        w = get_week(state, week_n)
        w["song_title"] = title.strip()
        w["song_artist"] = (artist or "").strip() or None
        w["difficulty"] = (difficulty or "").strip() or None
        save_state(state)
        label = w["song_title"]
        if w["song_artist"]:
            label = f"{label} — {w['song_artist']}"
        if w["difficulty"]:
            label = f"{label} ({w['difficulty']})"
        embed = build_admin_ok_embed(
            "Song set",
            f"Featured track updated for week **{week_n}**.",
            song=label,
            week=str(week_n),
        )
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- standings ---
    standings_grp = app_commands.Group(name="standings", description="Standings board", parent=rs)

    @standings_grp.command(name="update", description="Post or refresh public standings in the tourney channel")
    @admin_check()
    async def standings_update(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        channel = await _resolve_channel(bot, interaction)
        if not channel:
            await interaction.followup.send(
                "No tourney channel (set `RS_CHANNEL_ID` or run in a guild channel)."
            )
            return
        embeds = build_standings_embeds(state)
        msg_id = state.get("standings_message_id")
        msg = None
        file = logo_file()
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
                if file:
                    await msg.edit(content=None, embeds=embeds, attachments=[file])
                else:
                    await msg.edit(content=None, embeds=embeds, attachments=[])
            except (discord.NotFound, discord.HTTPException, ValueError):
                msg = None
        if msg is None:
            if file:
                msg = await channel.send(embeds=embeds, file=file)
            else:
                msg = await channel.send(embeds=embeds)
            state["standings_message_id"] = str(msg.id)
            save_state(state)
        await interaction.followup.send(f"Standings updated in {channel.mention}.")

    # --- team ---
    team_grp = app_commands.Group(name="team", description="Manage teams", parent=rs)

    @team_grp.command(name="add", description="Add a team of 2")
    @admin_check()
    @app_commands.describe(
        name="Team name",
        division="classic | fusion | arcade",
        captain="Captain (higher difficulty player)",
        teammate="Teammate",
    )
    @app_commands.choices(
        division=[
            app_commands.Choice(name="Classic", value="classic"),
            app_commands.Choice(name="Fusion", value="fusion"),
            app_commands.Choice(name="Arcade", value="arcade"),
        ]
    )
    async def team_add(
        interaction: discord.Interaction,
        name: str,
        division: app_commands.Choice[str],
        captain: discord.Member,
        teammate: discord.Member,
    ) -> None:
        state = get_state()
        div = normalize_division(division.value if hasattr(division, "value") else str(division))
        if not div:
            await interaction.response.send_message(
                f"Division must be one of: {', '.join(DIVISIONS)}", ephemeral=True
            )
            return
        if captain.id == teammate.id:
            await interaction.response.send_message(
                "Captain and teammate must be different people.", ephemeral=True
            )
            return
        if find_team_by_name(state, name):
            await interaction.response.send_message(
                "A team with that name already exists.", ephemeral=True
            )
            return
        for uid in (captain.id, teammate.id):
            if find_team_by_user(state, uid):
                await interaction.response.send_message(
                    f"<@{uid}> is already on a team.", ephemeral=True
                )
                return
        team = {
            "id": new_team_id(),
            "name": name.strip(),
            "division": div,
            "captain_user_id": str(captain.id),
            "teammate_user_id": str(teammate.id),
            "active": True,
        }
        state.setdefault("teams", []).append(team)
        save_state(state)
        embed = build_admin_ok_embed(
            "Team added",
            f"**{team['name']}** registered.",
            division=DIVISION_LABELS[div],
            captain=captain.mention,
            teammate=teammate.mention,
            id=f"`{team['id']}`",
        )
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @team_grp.command(name="replace", description="Replace captain or teammate on a team")
    @admin_check()
    @app_commands.describe(
        team_name="Exact team name",
        role="captain or teammate",
        new_player="Replacement Discord user",
    )
    @app_commands.choices(
        role=[
            app_commands.Choice(name="captain", value="captain"),
            app_commands.Choice(name="teammate", value="teammate"),
        ]
    )
    async def team_replace(
        interaction: discord.Interaction,
        team_name: str,
        role: app_commands.Choice[str],
        new_player: discord.Member,
    ) -> None:
        state = get_state()
        team = find_team_by_name(state, team_name)
        if not team:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return
        other = find_team_by_user(state, new_player.id)
        if other and other.get("id") != team.get("id"):
            await interaction.response.send_message(
                f"{new_player.mention} is already on **{other.get('name')}**.", ephemeral=True
            )
            return
        key = "captain_user_id" if role.value == "captain" else "teammate_user_id"
        old = team.get(key)
        team[key] = str(new_player.id)
        if team.get("captain_user_id") == team.get("teammate_user_id"):
            team[key] = old
            await interaction.response.send_message(
                "Captain and teammate cannot be the same.", ephemeral=True
            )
            return
        save_state(state)
        embed = build_admin_ok_embed(
            "Team updated",
            f"**{team['name']}** roster change.",
            role=role.value,
            was=f"<@{old}>",
            now=new_player.mention,
        )
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @team_grp.command(name="list", description="List registered teams")
    @admin_check()
    @app_commands.describe(division="Optional filter")
    @app_commands.choices(
        division=[
            app_commands.Choice(name="Classic", value="classic"),
            app_commands.Choice(name="Fusion", value="fusion"),
            app_commands.Choice(name="Arcade", value="arcade"),
        ]
    )
    async def team_list(
        interaction: discord.Interaction,
        division: app_commands.Choice[str] | None = None,
    ) -> None:
        state = get_state()
        teams = [t for t in state.get("teams") or [] if t.get("active", True)]
        if division:
            teams = [t for t in teams if t.get("division") == division.value]
        if not teams:
            await interaction.response.send_message("No teams registered.", ephemeral=True)
            return
        lines = []
        for t in sorted(
            teams, key=lambda x: ((x.get("division") or ""), (x.get("name") or "").lower())
        ):
            div = DIVISION_LABELS.get(t.get("division") or "", t.get("division"))
            lines.append(
                f"**{t.get('name')}** ({div}) · "
                f"C <@{t.get('captain_user_id')}> · T <@{t.get('teammate_user_id')}> · `{t.get('id')}`"
            )
        text = "\n".join(lines)
        if len(text) > 1900:
            text = "\n".join(lines[:40]) + f"\n… +{max(0, len(lines) - 40)} more"
        await interaction.response.send_message(text, ephemeral=True)

    # --- score (manual) ---
    score_grp = app_commands.Group(name="score", description="Manual score entry", parent=rs)

    @score_grp.command(name="set", description="Manually set a verified score (testing / disputes)")
    @admin_check()
    @app_commands.describe(
        player="Player on a registered team",
        score="Score value",
        week="Week 1–4 (default: current)",
    )
    async def score_set(
        interaction: discord.Interaction,
        player: discord.Member,
        score: app_commands.Range[int, 1, 99_999_999],
        week: app_commands.Range[int, 1, 4] | None = None,
    ) -> None:
        state = get_state()
        # Target week without moving season.current_week (go-live: don't
        # accidentally jump the tourney window when fixing a past score).
        sub, msg = record_submission(
            state,
            user_id=player.id,
            score=int(score),
            source="admin_manual",
            meta={"admin_id": str(interaction.user.id)},
            verified=True,
            approved_by=interaction.user.id,
            week=int(week) if week is not None else None,
        )
        if sub is None:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        embed = build_admin_ok_embed(
            "Manual score",
            f"{player.mention}: **{int(score):,}** (week {sub.get('week')})",
            id=f"`{sub.get('id')}`",
        )
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- submission ---
    sub_grp = app_commands.Group(name="submission", description="Approve pending scores", parent=rs)

    @sub_grp.command(name="approve", description="Approve a pending submission by id")
    @admin_check()
    @app_commands.describe(submission_id="Id from pending list (or omit to list pending)")
    async def submission_approve(
        interaction: discord.Interaction,
        submission_id: str | None = None,
    ) -> None:
        state = get_state()
        if not submission_id:
            pending = list_pending(state)
            if not pending:
                embed = build_admin_ok_embed(
                    "Pending submissions",
                    "No pending submissions this week.",
                )
                file = logo_file()
                if file:
                    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            lines = [
                f"`{s['id']}` · <@{s['user_id']}> · week {s['week']} · **{int(s['score']):,}**"
                for s in pending
            ]
            embed = build_admin_ok_embed(
                "Pending submissions",
                "Re-run with `submission_id` to approve.\n\n" + "\n".join(lines),
            )
            file = logo_file()
            if file:
                await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        _sub, msg = approve_submission(state, submission_id.strip(), interaction.user.id)
        embed = build_admin_ok_embed("Submission", msg)
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- dashboard ---
    dash_grp = app_commands.Group(name="dashboard", description="Public dashboard message", parent=rs)

    @dash_grp.command(name="post", description="Post or refresh the living dashboard")
    @admin_check()
    @app_commands.describe(pin="Pin the dashboard message (needs Manage Messages)")
    async def dashboard_post(
        interaction: discord.Interaction,
        pin: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        state = get_state()
        channel = await _resolve_channel(bot, interaction)
        if not channel:
            await interaction.followup.send("No tourney channel (set `RS_CHANNEL_ID`).")
            return
        embed = build_dashboard_embed(state)
        msg_id = state.get("dashboard_message_id")
        msg = None
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
                file = logo_file()
                if file:
                    await msg.edit(embed=embed, attachments=[file])
                else:
                    await msg.edit(embed=embed, attachments=[])
            except (discord.NotFound, discord.HTTPException, ValueError):
                msg = None
        if msg is None:
            file = logo_file()
            if file:
                msg = await channel.send(embed=embed, file=file)
            else:
                msg = await channel.send(embed=embed)
            state["dashboard_message_id"] = str(msg.id)
            save_state(state)
        pin_note = ""
        if pin and msg:
            pin_note = await _try_pin(msg)
        await interaction.followup.send(
            f"Dashboard posted in {channel.mention}.{pin_note}"
        )

    # --- calendar (Laura image calendars) ---
    cal_grp = app_commands.Group(name="calendar", description="Post official calendar images", parent=rs)

    @cal_grp.command(name="post", description="Post a calendar image (attach PNG/JPG) and optional pin")
    @admin_check()
    @app_commands.describe(
        image="Calendar image file",
        caption="Optional caption under the image",
        pin="Pin the calendar message",
    )
    async def calendar_post(
        interaction: discord.Interaction,
        image: discord.Attachment,
        caption: str | None = None,
        pin: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = await _resolve_channel(bot, interaction)
        if not channel:
            await interaction.followup.send("No tourney channel (set `RS_CHANNEL_ID`).")
            return
        ctype = (image.content_type or "").lower()
        name = (image.filename or "").lower()
        if not (
            ctype.startswith("image/")
            or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        ):
            await interaction.followup.send("Attachment must be an image (png/jpg/webp/gif).")
            return
        data = await image.read()
        if len(data) > 8_000_000:
            await interaction.followup.send("Image too large (max ~8 MB for Discord).")
            return
        fname = image.filename or "calendar.png"
        file = discord.File(fp=__import__("io").BytesIO(data), filename=fname)
        embed = build_announce_embed(
            get_state(),
            caption or "Official tournament calendar",
            style="default",
        )
        embed.set_image(url=f"attachment://{fname}")
        # logo + calendar: only calendar as main image
        files = [file]
        logo = logo_file()
        if logo:
            files.insert(0, logo)
            from theme import apply_logo_thumbnail

            apply_logo_thumbnail(embed)
        msg = await channel.send(embed=embed, files=files)
        state = get_state()
        state["calendar_message_id"] = str(msg.id)
        save_state(state)
        pin_note = await _try_pin(msg) if pin else ""
        await interaction.followup.send(f"Calendar posted in {channel.mention}.{pin_note}")

    # --- where (diagnostics) ---
    @rs.command(name="where", description="Show bot config / build (staff diagnostic)")
    @admin_check()
    async def where_cmd(interaction: discord.Interaction) -> None:
        state = get_state()
        season = state.get("season") or {}
        week_n = season.get("current_week")
        w = get_week(state, int(week_n or 1))
        lines = [
            f"**BOT_VERSION:** `{BOT_VERSION}`",
            f"**Guild env:** `{RS_GUILD_ID}`",
            f"**Channel env:** `{RS_CHANNEL_ID}`",
            f"**Submit env:** `{RS_SUBMIT_CHANNEL_ID}`",
            f"**Admin roles configured:** {len(RS_ADMIN_ROLE_IDS)}",
            f"**Season:** {season.get('name')} · week **{week_n}** · status **{w.get('status')}**",
            f"**Teams:** {len([t for t in state.get('teams') or [] if t.get('active', True)])}",
            f"**Submissions:** {len(state.get('submissions') or [])}",
            f"**Dashboard msg:** `{state.get('dashboard_message_id')}`",
            f"**Standings msg:** `{state.get('standings_message_id')}`",
            f"**Calendar msg:** `{state.get('calendar_message_id')}`",
        ]
        embed = build_admin_ok_embed("RS bot where", "\n".join(lines))
        file = logo_file()
        if file:
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- verse (H2H cards) ---
    verse_grp = app_commands.Group(
        name="verse",
        description="Post team-vs-team verse cards (daily HUD or big moments)",
        parent=rs,
    )

    @verse_grp.command(name="post", description="Post a verse card for two teams")
    @admin_check()
    @app_commands.describe(
        team_a="First team name (exact)",
        team_b="Second team name (exact)",
        style="daily=HUD (default); others=big moments",
        week="Week for scores (default: current)",
    )
    @app_commands.choices(
        style=[
            app_commands.Choice(name="daily (HUD) — default", value="daily"),
            app_commands.Choice(name="fight card — big moment", value="fight"),
            app_commands.Choice(name="drum ring — big moment", value="ring"),
            app_commands.Choice(name="poster — big moment", value="poster"),
            app_commands.Choice(name="result killscreen — big moment", value="result"),
            app_commands.Choice(name="title match — big moment", value="title"),
        ]
    )
    async def verse_post(
        interaction: discord.Interaction,
        team_a: str,
        team_b: str,
        style: app_commands.Choice[str] | None = None,
        week: app_commands.Range[int, 1, 4] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = await _resolve_channel(bot, interaction)
        if not channel:
            await interaction.followup.send("No tourney channel (set `RS_CHANNEL_ID`).")
            return
        state = get_state()
        ta = find_team_by_name(state, team_a)
        tb = find_team_by_name(state, team_b)
        if not ta:
            await interaction.followup.send(f"Team not found: **{team_a}**")
            return
        if not tb:
            await interaction.followup.send(f"Team not found: **{team_b}**")
            return
        if ta.get("id") == tb.get("id"):
            await interaction.followup.send("Pick two different teams.")
            return

        style_val = style.value if style else "daily"
        names_a = await _resolve_roster_names(bot, interaction.guild, ta)
        names_b = await _resolve_roster_names(bot, interaction.guild, tb)
        matchup = matchup_from_teams(
            state, ta, tb, week=week, name_a=names_a, name_b=names_b
        )
        try:
            png = render_verse(matchup, style_val)  # type: ignore[arg-type]
        except Exception as e:
            print(f"Verse render failed: {e}")
            await interaction.followup.send(f"Verse render failed: `{e}`")
            return

        label = STYLE_LABELS.get(style_val, style_val)
        # Public post: image as main art, light embed caption
        public = discord.Embed(
            title=f"{matchup.side_a.name}  vs  {matchup.side_b.name}",
            description=(
                f"**{label}** · Week {matchup.week} · {matchup.season}\n"
                f"`{_fmt_score_simple(matchup.side_a.score)}` — `{_fmt_score_simple(matchup.side_b.score)}`\n"
                f"Highest verified team score wins."
            ),
            color=0xE10600,
        )
        public.set_image(url=f"attachment://{VERSE_ATTACHMENT_NAME}")
        public.set_footer(text="RS verse card · /rs verse post")
        from theme import apply_logo_thumbnail

        apply_logo_thumbnail(public)

        verse_file = verse_discord_file(png)
        files = files_for_embeds(verse_file)
        await channel.send(embed=public, files=files)
        await interaction.followup.send(
            f"Posted **{label}** verse in {channel.mention}: "
            f"**{matchup.side_a.name}** vs **{matchup.side_b.name}** "
            f"({_fmt_score_simple(matchup.side_a.score)} — {_fmt_score_simple(matchup.side_b.score)})."
        )

    # --- announce ---
    @rs.command(name="announce", description="Post a staff announcement in the tourney channel")
    @admin_check()
    @app_commands.describe(
        message="Announcement text",
        style="Visual style (default uses hero banner)",
    )
    @app_commands.choices(
        style=[
            app_commands.Choice(name="default (hero + ops)", value="default"),
            app_commands.Choice(name="week open", value="week_open"),
            app_commands.Choice(name="week close", value="week_close"),
            app_commands.Choice(name="captain burden", value="burden"),
            app_commands.Choice(name="embed only", value="embed_only"),
        ]
    )
    async def announce(
        interaction: discord.Interaction,
        message: str,
        style: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = await _resolve_channel(bot, interaction)
        if not channel:
            await interaction.followup.send("No tourney channel (set `RS_CHANNEL_ID`).")
            return
        state = get_state()
        style_val = style.value if style else "default"
        await _post_announce(channel, state, message, style=style_val)
        await interaction.followup.send(f"Announced in {channel.mention} ({style_val}).")

    tree.add_command(rs)


def _fmt_score_simple(n: int) -> str:
    return f"{int(n):,}"


async def _resolve_roster_names(
    bot: discord.Client,
    guild: discord.Guild | None,
    team: dict,
) -> tuple[str, str]:
    """Best-effort display names for captain / teammate."""

    async def one(uid: str | None, fallback: str) -> str:
        if not uid:
            return fallback
        # try cache
        if guild:
            member = guild.get_member(int(uid))
            if member:
                return member.display_name
            try:
                member = await guild.fetch_member(int(uid))
                return member.display_name
            except (discord.HTTPException, ValueError):
                pass
        try:
            user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
            return user.display_name or user.name or fallback
        except (discord.HTTPException, ValueError):
            return fallback

    cap = await one(team.get("captain_user_id"), "Captain")
    mate = await one(team.get("teammate_user_id"), "Teammate")
    return cap, mate


async def _post_week_announce(
    channel: discord.abc.Messageable,
    state: dict,
    *,
    style: str,
) -> None:
    week_n = int(state.get("season", {}).get("current_week") or 1)
    if style == "week_open":
        msg = (
            f"Week **{week_n}** scoring is **OPEN**.\n"
            "Pair up, hit the chart, and put points on the board.\n"
            "Players: `/tourney status` · `/tourney my-score`"
        )
    else:
        msg = (
            f"Week **{week_n}** is **CLOSED**.\n"
            "Late scores need staff approval (`/rs submission approve`)."
        )
    await _post_announce(channel, state, msg, style=style)


async def _post_announce(
    channel: discord.abc.Messageable,
    state: dict,
    message: str,
    *,
    style: str = "default",
) -> None:
    embed_style = style if style != "embed_only" else "default"
    if style == "embed_only":
        embed_style = "default"
    embed = build_announce_embed(state, message, style=embed_style)

    use_hero = style != "embed_only"
    hero_file = None
    if use_hero:
        try:
            mode = "burden" if style == "burden" else "week"
            if style == "default":
                mode = "announce"
            png = render_hero_from_state(state, mode=mode)
            # Force closed visual for week_close
            if style == "week_close":
                from render_banners import render_hero_banner
                from config import CAPTAIN_BURDEN_WEEK
                from state import get_week

                week_n = int(state.get("season", {}).get("current_week") or 1)
                week = get_week(state, week_n)
                song = week.get("song_title")
                if song and week.get("song_artist"):
                    song = f"{song} — {week['song_artist']}"
                png = render_hero_banner(
                    week=week_n,
                    season=(state.get("season") or {}).get("name") or "Season 1",
                    status="closed",
                    song=song,
                    deadline=None,
                    burden=week_n == CAPTAIN_BURDEN_WEEK,
                )
            hero_file = hero_discord_file(png, HERO_ATTACHMENT_NAME)
            # Attach hero as image in embed
            embed.set_image(url=f"attachment://{HERO_ATTACHMENT_NAME}")
        except Exception as e:
            print(f"Hero banner render failed: {e}")
            hero_file = None

    files = files_for_embeds(hero_file)
    if files:
        await channel.send(embed=embed, files=files)
    else:
        await channel.send(embed=embed)


async def _resolve_channel(
    bot: discord.Client, interaction: discord.Interaction
) -> discord.TextChannel | discord.Thread | None:
    if RS_CHANNEL_ID:
        ch = bot.get_channel(RS_CHANNEL_ID)
        if ch is None:
            try:
                ch = await bot.fetch_channel(RS_CHANNEL_ID)
            except discord.HTTPException:
                ch = None
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            return ch
    if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
        return interaction.channel
    return None


async def _try_pin(msg: discord.Message) -> str:
    """Best-effort pin; returns short note for staff followup."""
    try:
        await msg.pin(reason="RS Tourney Bot")
        return " Pinned."
    except discord.Forbidden:
        return " (could not pin — need Manage Messages)"
    except discord.HTTPException as e:
        # Already pinned or pin cap
        return f" (pin skipped: {e})"
