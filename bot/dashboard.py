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
    DASH_STRIP_NAME,
    EMBED_COLOR,
    OPS_STRIP_NAME,
    STANDINGS_ATTACHMENT_NAME,
    apply_logo_thumbnail,
    base_embed,
    chip_line,
    footer_player,
    footer_public,
    footer_rs4l,
    footer_staff,
    fmt_score,
    logo_file,
    pill_line,
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
        from rules import division_has_captain_role, roster_labels

        div = t.get("division")
        if division_has_captain_role(div):
            slots = (("C", t.get("captain_user_id")), ("T", t.get("teammate_user_id")))
        else:
            # Fusion: both captains (still a duo) — C·A / C·B for missing list
            slots = (("C·A", t.get("captain_user_id")), ("C·B", t.get("teammate_user_id")))
        for role, uid in slots:
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


def build_dashboard_embed(state: dict[str, Any], *, with_image: bool = True) -> discord.Embed:
    """Ops-dashboard style living board (mockup 01 + 04 language)."""
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    status_raw = (week.get("status") or "scheduled").lower()
    # Burden is Classic/Arcade only (Fusion: both captains → no teammate bonus)
    burden = week_n == CAPTAIN_BURDEN_WEEK

    status_chip = "OPEN" if status_raw == "open" else ("CLOSED" if status_raw == "closed" else "SCHEDULED")
    pills = pill_line(
        f"WEEK {week_n}",
        status_chip,
        "BURDEN · CLASSIC/ARCADE" if burden else "CLASSIC · FUSION · ARCADE",
    )
    body = (
        f"Living tournament board for **{season_name(state)}**.\n"
        f"Song, deadlines, missing scores, and standings peek — all in one place.\n\n"
        f"{pills}"
    )

    embed = base_embed(
        title=f"Week {week_n} dashboard",
        description=body,
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
            value=(
                "**ACTIVE** (Classic / Arcade) — Captain + (Teammate × 2). "
                "**Fusion:** both are captains (no teammate) — plain sum, no Burden bonus."
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="Captain's Burden",
            value=f"Week {CAPTAIN_BURDEN_WEEK} · Classic/Arcade only (Fusion: both captains)",
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

    if with_image:
        embed.set_image(url=f"attachment://{DASH_STRIP_NAME}")
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · DASHBOARD"))
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


def build_standings_embeds(
    state: dict[str, Any],
    division: str | None = None,
    *,
    with_image: bool = True,
) -> list[discord.Embed]:
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    subs = state.get("submissions") or []
    teams = state.get("teams") or []
    divs = [division] if division else list(DIVISIONS)
    embeds: list[discord.Embed] = []

    # Lead card — graphic + summary (mockup-quality image attaches separately)
    lead = base_embed(
        title=f"{season_name(state)} standings",
        description=(
            f"Cumulative through **week {week_n}**.\n"
            f"{pill_line('BEST VERIFIED', 'MISSING = 0', 'TEAMS OF 2')}"
        ),
        thumbnail=True,
    )
    if with_image:
        lead.set_image(url=f"attachment://{STANDINGS_ATTACHMENT_NAME}")
    lead.set_footer(text=footer_rs4l("RS TOURNEY BOT · STANDINGS"))
    embeds.append(lead)

    for div in divs:
        if div not in DIVISIONS:
            continue
        rows = standings_rows(teams, subs, div, through_week=week_n)
        label = DIVISION_LABELS.get(div, div)
        embed = base_embed(
            title=f"{label}",
            description=f"Division board · week **{week_n}**",
            thumbnail=False,
            author="RHYTHM SYNDICATE · STANDINGS",
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
        embed.set_footer(text=footer_public("division board"))
        embeds.append(embed)

    if len(embeds) == 1:
        # only lead with empty divisions
        pass
    return embeds


def build_team_embed(
    state: dict[str, Any],
    team: dict[str, Any],
    *,
    with_image: bool = True,
) -> discord.Embed:
    from rules import team_season_total
    from theme import TEAM_CARD_NAME

    week_n = int(state.get("season", {}).get("current_week") or 1)
    subs = state.get("submissions") or []
    div_key = (team.get("division") or "").lower()
    bd = team_week_breakdown(
        subs,
        team.get("captain_user_id"),
        team.get("teammate_user_id"),
        week_n,
        division=div_key,
    )
    season_tot = team_season_total(
        subs,
        team.get("captain_user_id"),
        team.get("teammate_user_id"),
        through_week=week_n,
        division=div_key,
    )
    div = DIVISION_LABELS.get(div_key, team.get("division"))
    slot1 = str(bd.get("slot1_label") or "Captain")
    slot2 = str(bd.get("slot2_label") or "Teammate")
    pills = pill_line(
        *[
            p
            for p in (
                str(div).upper() if div else "TEAM",
                f"WEEK {week_n}",
                "ACTIVE" if team.get("active", True) else "INACTIVE",
                "BOTH CAPTAINS" if not bd.get("has_captain_role") else "",
                "CAPTAIN'S BURDEN" if bd["captain_burden"] else "",
            )
            if p
        ]
    )
    embed = base_embed(
        title=team.get("name") or "Team",
        description=f"Your roster and week totals.\n\n{pills}",
        thumbnail=True,
        author="RHYTHM SYNDICATE · TEAM",
    )
    cap_uid = team.get("captain_user_id")
    mate_uid = team.get("teammate_user_id")
    embed.add_field(
        name=slot1,
        value=f"<@{cap_uid}>" if cap_uid else "—",
        inline=True,
    )
    embed.add_field(
        name=slot2,
        value=f"<@{mate_uid}>" if mate_uid else "—",
        inline=True,
    )
    embed.add_field(name="Division", value=str(div), inline=True)
    embed.add_field(name=f"{slot1} score", value=fmt_score(bd["captain_score"]), inline=True)
    embed.add_field(name=f"{slot2} score", value=fmt_score(bd["teammate_score"]), inline=True)
    label = "Team total (Captain's Burden)" if bd["captain_burden"] else "Team total"
    embed.add_field(name=label, value=f"**{fmt_score(bd['team_total'])}**", inline=True)
    embed.add_field(name="Season total", value=f"**{fmt_score(season_tot)}**", inline=True)
    if with_image:
        embed.set_image(url=f"attachment://{TEAM_CARD_NAME}")
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · TEAM"))
    return embed


def build_score_embed(
    state: dict[str, Any],
    team: dict[str, Any],
    user_id: int | str,
    *,
    with_image: bool = True,
) -> discord.Embed:
    from rules import player_week_score, team_season_total
    from theme import SCORE_FLASH_NAME

    week_n = int(state.get("season", {}).get("current_week") or 1)
    subs = state.get("submissions") or []
    div_key = (team.get("division") or "").lower()
    mine = player_week_score(subs, user_id, week_n)
    bd = team_week_breakdown(
        subs,
        team.get("captain_user_id"),
        team.get("teammate_user_id"),
        week_n,
        division=div_key,
    )
    season_tot = team_season_total(
        subs,
        team.get("captain_user_id"),
        team.get("teammate_user_id"),
        through_week=week_n,
        division=div_key,
    )
    slot1 = str(bd.get("slot1_label") or "Captain")
    slot2 = str(bd.get("slot2_label") or "Teammate")
    pills = pill_line(
        f"WEEK {week_n}",
        "BEST VERIFIED",
        "BURDEN ON" if bd["captain_burden"] else (
            "FUSION · BOTH CAPTAINS" if not bd.get("has_captain_role") else "STANDARD SCORING"
        ),
    )
    embed = base_embed(
        title="Your score",
        description=f"**{team.get('name') or 'Team'}**\n\n{pills}",
        thumbnail=True,
        author="RHYTHM SYNDICATE · SCORES",
    )
    embed.add_field(name="Your best (verified)", value=f"**{fmt_score(mine)}**", inline=False)
    embed.add_field(name=f"{slot1} this week", value=fmt_score(bd["captain_score"]), inline=True)
    embed.add_field(name=f"{slot2} this week", value=fmt_score(bd["teammate_score"]), inline=True)
    embed.add_field(name="Team week total", value=f"**{fmt_score(bd['team_total'])}**", inline=True)
    embed.add_field(name="Season total", value=f"**{fmt_score(season_tot)}**", inline=True)
    if bd["captain_burden"]:
        embed.add_field(
            name="Captain's Burden",
            value="⚡ Active: Captain + (Teammate × 2)",
            inline=False,
        )
    elif not bd.get("has_captain_role"):
        embed.add_field(
            name="Fusion",
            value="Both players are **captains** (no teammate role) — scores sum 1:1, **no Burden bonus**.",
            inline=False,
        )
    if with_image:
        embed.set_image(url=f"attachment://{SCORE_FLASH_NAME}")
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · SCORES"))
    return embed


def build_rules_embed() -> discord.Embed:
    text = (
        f"{pill_line('SEASON 1', '4 WEEKS', '3 DIVISIONS')}\n\n"
        "**Divisions:** Classic · Fusion · Arcade\n"
        "**Classic / Arcade:** teams of 2 — **Captain** + **Teammate**\n"
        "**Fusion:** still a duo — **both are captains** (no teammate role); **no Burden bonus**\n"
        "**Schedule** — song reveal Sat 10:00 AM PST · deadline Fri 11:59 PM PST\n"
        "Unlimited attempts — only the **highest verified** score counts\n"
        "Missing partner score = **0** (entry stays active)\n"
        "Late scores need **staff approval**\n"
        f"**Week {CAPTAIN_BURDEN_WEEK} Captain's Burden** (Classic / Arcade only): "
        "Captain + (Teammate × 2)\n"
        "Registration via Sesh · staff import teams after close"
    )
    embed = base_embed(
        title="Season 1 rules",
        description=text,
        thumbnail=True,
        author="RHYTHM SYNDICATE · RULES",
    )
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · RULES"))
    return embed


def build_help_embed() -> discord.Embed:
    from config import BOT_VERSION

    text = (
        f"**Build** `{BOT_VERSION}`\n\n"
        f"{pill_line('PLAYERS', '/tourney', 'STAFF /rs')}\n\n"
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
        title="Tournament Bot",
        description=text,
        thumbnail=True,
    )
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · HELP"))
    return embed


def build_announce_embed(
    state: dict[str, Any],
    message: str,
    *,
    style: str = "default",
) -> discord.Embed:
    """
    Ops-strip announcement embed (mockup 01 + 04).
    style: default | week_open | week_close | burden
    """
    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    status_raw = (week.get("status") or "scheduled").lower()
    burden = week_n == CAPTAIN_BURDEN_WEEK or style == "burden"

    if style == "week_open":
        title = f"Season 1 · Week {week_n} is LIVE"
        pills = pill_line(f"WEEK {week_n} OPEN", "SAT 10:00 AM PST", "CLASSIC · FUSION · ARCADE")
    elif style == "week_close":
        title = f"Week {week_n} is CLOSED"
        pills = pill_line(f"WEEK {week_n} CLOSED", "LATES NEED APPROVAL")
    elif style == "burden" or (burden and style == "week_open"):
        title = f"Captain's Burden · Week {week_n}"
        pills = pill_line("CLASSIC / ARCADE", "CAPTAIN + TEAMMATE × 2", "FUSION: BOTH CAPTAINS")
    else:
        title = "Official announcement"
        pills = pill_line(season_name(state), f"WEEK {week_n}", status_label(status_raw).replace("● ", "").replace("○ ", ""))

    embed = base_embed(
        title=title,
        description=f"{message}\n\n{pills}",
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
            value=(
                "**ACTIVE** for Classic / Arcade — Captain + (Teammate × 2).\n"
                "**Fusion:** both captains (no teammate) — plain sum, no Burden bonus."
            ),
            inline=False,
        )
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · ANNOUNCEMENT"))
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
    embed = base_embed(
        title=title,
        description=description,
        thumbnail=True,
        author="RHYTHM SYNDICATE · STAFF",
    )
    for name, value in fields.items():
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
        pills = pill_line("VERIFIED", "COUNTS TOWARD BEST")
    else:
        title = "Score pending"
        color = 0x8B929A  # steel — awaiting staff
        pills = pill_line("PENDING", "STAFF APPROVAL")
    embed = base_embed(
        title=title,
        description=f"{status_text}\n\n{pills}",
        color=color,
        thumbnail=True,
        author="RHYTHM SYNDICATE · SCORE INTAKE",
    )
    if score is not None:
        embed.add_field(name="Score", value=f"**{fmt_score(score)}**", inline=True)
    if week is not None:
        embed.add_field(name="Week", value=str(week), inline=True)
    embed.set_footer(text=footer_rs4l("RS TOURNEY BOT · SCORES"))
    return embed
