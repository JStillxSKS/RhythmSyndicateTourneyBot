"""Living dashboard, standings, team cards, and announcement embeds (visual layer)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import discord

from config import (
    CAPTAIN_BURDEN_WEEK,
    DIVISION_LABELS,
    DIVISIONS,
    SEASON_WEEKS,
)
from rules import standings_rows, team_week_breakdown
from state import get_week
from theme import (
    EMBED_COLOR,
    apply_logo_thumbnail,
    base_embed,
    chip_line,
    footer_player,
    footer_public,
    footer_staff,
    fmt_score,
    logo_file,
    rank_prefix,
    season_name,
    status_label,
)

# Re-export for callers that imported logo_file from dashboard
__all__ = [
    "logo_file",
    "time_remaining_text",
    "missing_submissions",
    "build_dashboard_embed",
    "build_standings_embeds",
    "build_team_embed",
    "build_score_embed",
    "build_rules_embed",
    "build_help_embed",
    "build_announce_embed",
    "build_week_status_embed",
    "build_admin_ok_embed",
    "build_submission_reply_embed",
]


def _fmt_deadline(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        from config import RS_TZ

        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        local = dt.astimezone(RS_TZ)
        return local.strftime("%a %b %d · %I:%M %p %Z")
    except ValueError:
        return iso


def time_remaining_text(close_at: str | None, status: str) -> str:
    if status != "open" or not close_at:
        return "—"
    try:
        end = datetime.fromisoformat(close_at.replace("Z", "+00:00"))
        now = datetime.now(tz=end.tzinfo)
        sec = int((end - now).total_seconds())
        if sec <= 0:
            return "Deadline passed"
        days, rem = divmod(sec, 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        if days:
            return f"{days}d {hours}h {mins}m"
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    except ValueError:
        return "—"


def missing_submissions(state: dict[str, Any], week: int | None = None) -> list[str]:
    """Players on active teams with no verified score this week."""
    from rules import player_week_score

    w = int(week if week is not None else state.get("season", {}).get("current_week") or 1)
    subs = state.get("submissions") or []
    lines: list[str] = []
    for t in state.get("teams") or []:
        if not t.get("active", True):
            continue
        name = t.get("name") or "Team"
        for role, uid in (("C", t.get("captain_user_id")), ("T", t.get("teammate_user_id"))):
            if not uid:
                continue
            if player_week_score(subs, uid, w) <= 0:
                lines.append(f"{name} · {role} <@{uid}>")
    return lines


def _song_label(week: dict[str, Any]) -> str:
    song = week.get("song_title") or "TBD"
    if week.get("song_artist"):
        song = f"{song} — {week['song_artist']}"
    if week.get("difficulty"):
        song = f"{song} ({week['difficulty']})"
    return song


def build_dashboard_embed(state: dict[str, Any]) -> discord.Embed:
    """Ops-dashboard style living board (mockup 04 language)."""
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    status_raw = (week.get("status") or "scheduled").lower()
    burden = week_n == CAPTAIN_BURDEN_WEEK

    desc_bits = [
        f"**Week {week_n}** / {SEASON_WEEKS}",
        status_label(status_raw),
    ]
    if burden:
        desc_bits.append("⚡ **Captain's Burden ACTIVE**")

    embed = base_embed(
        title=f"Rhythm Syndicate · {season_name(state)}",
        description=chip_line(*desc_bits),
        thumbnail=True,
    )

    embed.add_field(
        name="Featured song",
        value=f"**{_song_label(week)}**",
        inline=False,
    )
    embed.add_field(name="Opens", value=_fmt_deadline(week.get("open_at")), inline=True)
    embed.add_field(name="Deadline", value=_fmt_deadline(week.get("close_at")), inline=True)
    embed.add_field(
        name="Time left",
        value=f"**{time_remaining_text(week.get('close_at'), status_raw)}**",
        inline=True,
    )

    if burden:
        embed.add_field(
            name="Captain's Burden",
            value="**ACTIVE** — Team score = Captain + (Teammate × 2)",
            inline=False,
        )
    else:
        embed.add_field(
            name="Captain's Burden",
            value=f"Week {CAPTAIN_BURDEN_WEEK} only",
            inline=True,
        )
        embed.add_field(
            name="Divisions",
            value="Classic · Fusion · Arcade",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)

    missing = missing_submissions(state, week_n)
    if status_raw == "open":
        if missing:
            text = _pack_field_lines(missing, more_label="more")
            embed.add_field(name=f"Missing scores ({len(missing)})", value=text, inline=False)
        else:
            embed.add_field(
                name="Missing scores",
                value="✅ None — all players on the board",
                inline=False,
            )

    peeks: list[str] = []
    subs = state.get("submissions") or []
    teams = state.get("teams") or []
    for div in DIVISIONS:
        rows = standings_rows(teams, subs, div, through_week=week_n)[:3]
        if not rows:
            peeks.append(f"**{DIVISION_LABELS[div]}** — *no teams*")
            continue
        lines = [f"{rank_prefix(r['rank'])} {r['name']} — **{fmt_score(r['total'])}**" for r in rows]
        peeks.append(f"**{DIVISION_LABELS[div]}**\n" + "\n".join(lines))
    embed.add_field(name="Standings · top 3", value="\n\n".join(peeks) or "—", inline=False)

    embed.set_footer(text=footer_public("living dashboard"))
    return embed


def _pack_field_lines(lines: list[str], *, limit: int = 1024, more_label: str = "more") -> str:
    """Discord field values max 1024 chars — never blow the API on big boards."""
    if not lines:
        return "—"
    out: list[str] = []
    used = 0
    for i, line in enumerate(lines):
        extra = len(line) + (1 if out else 0)
        # Reserve room for a possible "+N more" footer
        remaining_after = len(lines) - i - 1
        footer_budget = 20 if remaining_after > 0 else 0
        if out and used + extra + footer_budget > limit:
            left = len(lines) - i
            out.append(f"… +{left} {more_label}")
            break
        if not out and len(line) > limit:
            out.append(line[: limit - 1] + "…")
            break
        out.append(line)
        used += extra
    text = "\n".join(out)
    return text[:limit] if len(text) > limit else text


def build_standings_embeds(state: dict[str, Any], division: str | None = None) -> list[discord.Embed]:
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    subs = state.get("submissions") or []
    teams = state.get("teams") or []
    divs = [division] if division else list(DIVISIONS)
    embeds: list[discord.Embed] = []

    for div in divs:
        if div not in DIVISIONS:
            continue
        rows = standings_rows(teams, subs, div, through_week=week_n)
        label = DIVISION_LABELS.get(div, div)
        embed = base_embed(
            title=f"{label} standings",
            description=f"{season_name(state)} · cumulative through **week {week_n}**",
            thumbnail=False,
        )
        if not rows:
            embed.add_field(name="Board", value="*No teams in this division yet.*", inline=False)
        else:
            lines = [
                f"{rank_prefix(int(r['rank']))} **{r['name']}** — {fmt_score(r['total'])}"
                for r in rows
            ]
            embed.add_field(
                name=f"{len(rows)} team(s)",
                value=_pack_field_lines(lines, more_label="teams"),
                inline=False,
            )
        embed.set_footer(text=footer_public("best verified · missing teammate = 0"))
        embeds.append(embed)

    if not embeds:
        embeds = [base_embed(title="Standings", description="No data.", thumbnail=False)]
    # Logo only on first board to avoid re-upload spam
    if embeds:
        apply_logo_thumbnail(embeds[0])
    return embeds


def build_team_embed(state: dict[str, Any], team: dict[str, Any]) -> discord.Embed:
    week_n = int(state.get("season", {}).get("current_week") or 1)
    subs = state.get("submissions") or []
    bd = team_week_breakdown(
        subs, team.get("captain_user_id"), team.get("teammate_user_id"), week_n
    )
    div = DIVISION_LABELS.get((team.get("division") or "").lower(), team.get("division"))
    embed = base_embed(
        title=team.get("name") or "Team",
        description=f"Division **{div}** · Week **{week_n}**",
        thumbnail=True,
    )
    embed.add_field(name="Captain", value=f"<@{team.get('captain_user_id')}>", inline=True)
    embed.add_field(name="Teammate", value=f"<@{team.get('teammate_user_id')}>", inline=True)
    embed.add_field(name="Status", value="Active" if team.get("active", True) else "Inactive", inline=True)
    embed.add_field(name="Captain score", value=fmt_score(bd["captain_score"]), inline=True)
    embed.add_field(name="Teammate score", value=fmt_score(bd["teammate_score"]), inline=True)
    label = "Team total (Captain's Burden)" if bd["captain_burden"] else "Team total"
    embed.add_field(name=label, value=f"**{fmt_score(bd['team_total'])}**", inline=True)
    if bd["captain_burden"]:
        embed.add_field(
            name="Captain's Burden",
            value="Captain + (Teammate × 2) this week",
            inline=False,
        )
    embed.set_footer(text=footer_player())
    return embed


def build_score_embed(
    state: dict[str, Any],
    team: dict[str, Any],
    user_id: int | str,
) -> discord.Embed:
    from rules import player_week_score, team_season_total

    week_n = int(state.get("season", {}).get("current_week") or 1)
    subs = state.get("submissions") or []
    mine = player_week_score(subs, user_id, week_n)
    bd = team_week_breakdown(
        subs, team.get("captain_user_id"), team.get("teammate_user_id"), week_n
    )
    season_tot = team_season_total(
        subs, team.get("captain_user_id"), team.get("teammate_user_id"), through_week=week_n
    )
    embed = base_embed(
        title="Your score",
        description=f"**{team.get('name') or 'Team'}** · Week **{week_n}**",
        thumbnail=True,
    )
    embed.add_field(name="Your best (verified)", value=f"**{fmt_score(mine)}**", inline=False)
    embed.add_field(name="Captain this week", value=fmt_score(bd["captain_score"]), inline=True)
    embed.add_field(name="Teammate this week", value=fmt_score(bd["teammate_score"]), inline=True)
    embed.add_field(name="Team week total", value=f"**{fmt_score(bd['team_total'])}**", inline=True)
    embed.add_field(name="Season total", value=f"**{fmt_score(season_tot)}**", inline=True)
    if bd["captain_burden"]:
        embed.add_field(
            name="Captain's Burden",
            value="⚡ Active: Captain + (Teammate × 2)",
            inline=False,
        )
    embed.set_footer(text=footer_player())
    return embed


def build_rules_embed() -> discord.Embed:
    text = (
        "**Divisions:** Classic · Fusion · Arcade\n"
        "**Teams of 2** (same division only)\n"
        "**4 weeks** — song reveal Sat 10:00 AM PST · deadline Fri 11:59 PM PST\n"
        "Unlimited attempts — only the **highest verified** score counts\n"
        "Missing teammate score = **0** (team stays active)\n"
        "Late scores need **staff approval**\n"
        f"**Week {CAPTAIN_BURDEN_WEEK} Captain's Burden:** Captain + (Teammate × 2)\n"
        "Registration via Sesh · staff import teams after close"
    )
    embed = base_embed(title="Season 1 rules", description=text, thumbnail=True)
    embed.set_footer(text=footer_public())
    return embed


def build_help_embed() -> discord.Embed:
    from config import BOT_VERSION

    text = (
        f"**Build** `{BOT_VERSION}`\n\n"
        "**Player commands**\n"
        "`/tourney status` — week, song, deadline\n"
        "`/tourney my-team` — your team\n"
        "`/tourney my-score` — your scores\n"
        "`/tourney standings` — leaderboards\n"
        "`/tourney rules` — Season 1 rules\n"
        "`/tourney help` — this message\n\n"
        "Forward a Smash Drums **score embed** in the tourney channel to submit.\n"
        "Staff commands use `/rs`."
    )
    embed = base_embed(
        title="Rhythm Syndicate Tournament Bot",
        description=text,
        thumbnail=True,
    )
    embed.set_footer(text=footer_player())
    return embed


def build_announce_embed(
    state: dict[str, Any],
    message: str,
    *,
    style: str = "default",
) -> discord.Embed:
    """
    Ops-strip announcement embed (mockup 04).
    style: default | week_open | week_close | burden
    """
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    status_raw = (week.get("status") or "scheduled").lower()
    burden = week_n == CAPTAIN_BURDEN_WEEK or style == "burden"

    if style == "week_open":
        title = f"Week {week_n} is OPEN"
        head = status_label("open")
    elif style == "week_close":
        title = f"Week {week_n} is CLOSED"
        head = status_label("closed")
    elif style == "burden" or burden and style == "week_open":
        title = f"Captain's Burden · Week {week_n}"
        head = "⚡ Special scoring week"
    else:
        title = "Rhythm Syndicate · Announcement"
        head = season_name(state)

    embed = base_embed(
        title=title,
        description=f"{head}\n\n{message}",
        thumbnail=True,
    )
    embed.add_field(name="Week", value=f"**{week_n}** / {SEASON_WEEKS}", inline=True)
    embed.add_field(name="Status", value=status_label(status_raw), inline=True)
    embed.add_field(
        name="Time left",
        value=time_remaining_text(week.get("close_at"), status_raw),
        inline=True,
    )
    embed.add_field(name="Featured song", value=_song_label(week), inline=False)
    embed.add_field(name="Opens", value=_fmt_deadline(week.get("open_at")), inline=True)
    embed.add_field(name="Deadline", value=_fmt_deadline(week.get("close_at")), inline=True)
    embed.add_field(name="Divisions", value="Classic · Fusion · Arcade", inline=True)
    if burden:
        embed.add_field(
            name="Captain's Burden",
            value="**ACTIVE** — Captain + (Teammate × 2)",
            inline=False,
        )
    embed.set_footer(text=footer_staff())
    return embed


def build_week_status_embed(
    state: dict[str, Any],
    week_n: int,
    *,
    opened: bool,
) -> discord.Embed:
    week = get_week(state, week_n)
    if opened:
        title = f"Week {week_n} opened"
        desc = "Scoring window is **OPEN**. Players can submit verified scores."
    else:
        title = f"Week {week_n} closed"
        desc = "Scoring window is **CLOSED**. Late scores need `/rs submission approve`."
    embed = base_embed(title=title, description=desc, thumbnail=True)
    embed.add_field(name="Song", value=_song_label(week), inline=False)
    embed.add_field(name="Deadline", value=_fmt_deadline(week.get("close_at")), inline=True)
    embed.add_field(name="Status", value=status_label(week.get("status")), inline=True)
    if week_n == CAPTAIN_BURDEN_WEEK:
        embed.add_field(
            name="Captain's Burden",
            value="Captain + (Teammate × 2)",
            inline=False,
        )
    embed.set_footer(text=footer_staff())
    return embed


def build_admin_ok_embed(title: str, description: str, **fields: str) -> discord.Embed:
    embed = base_embed(title=title, description=description, thumbnail=True)
    for name, value in fields.items():
        # field names: use human labels; keys with _ become spaces
        label = name.replace("_", " ").title()
        embed.add_field(name=label, value=value, inline=True)
    embed.set_footer(text=footer_staff())
    return embed


def build_submission_reply_embed(
    *,
    verified: bool,
    status_text: str,
    score: int | None = None,
    week: int | None = None,
) -> discord.Embed:
    if verified:
        title = "Score verified"
        color = EMBED_COLOR
    else:
        title = "Score pending"
        color = 0xC5CCD4  # steel — awaiting staff
    embed = discord.Embed(title=title, description=status_text, color=color)
    if score is not None:
        embed.add_field(name="Score", value=fmt_score(score), inline=True)
    if week is not None:
        embed.add_field(name="Week", value=str(week), inline=True)
    apply_logo_thumbnail(embed)
    embed.set_footer(text=footer_public("score intake"))
    return embed
