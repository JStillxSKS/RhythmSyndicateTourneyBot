"""Rhythm Syndicate brand kit — single source for colors, footers, status language."""
from __future__ import annotations

from typing import Any

import discord

from config import BOT_VERSION, LOGO_PATH, RS_EMBED_COLOR, RS_RED

# ---------------------------------------------------------------------------
# Palette (logo: red / black / steel)
# ---------------------------------------------------------------------------

RS_RED_HEX = 0xE10600
RS_STEEL_HEX = 0xC5CCD4
RS_BLACK_HEX = 0x0A0A0A
RS_CARD_HEX = 0x121417

# Keep config alias as source of truth for embed side-color
EMBED_COLOR = RS_EMBED_COLOR or RS_RED or RS_RED_HEX

LOGO_ATTACHMENT_NAME = "rhythm-syndicate-logo.jpg"
HERO_ATTACHMENT_NAME = "rs-announce-hero.png"
STANDINGS_ATTACHMENT_NAME = "rs-standings.png"
VERSE_ATTACHMENT_NAME = "rs-verse-card.png"
OPS_STRIP_NAME = "rs-ops-strip.png"
DASH_STRIP_NAME = "rs-dashboard-strip.png"
SCORE_FLASH_NAME = "rs-score-flash.png"
TEAM_CARD_NAME = "rs-team-card.png"

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_SCHEDULED = "scheduled"

STATUS_LABEL = {
    STATUS_OPEN: "● OPEN",
    STATUS_CLOSED: "● CLOSED",
    STATUS_SCHEDULED: "○ SCHEDULED",
}

RANK_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def status_label(raw: str | None) -> str:
    key = (raw or STATUS_SCHEDULED).lower().strip()
    return STATUS_LABEL.get(key, f"○ {key.upper()}")


def footer_public(extra: str | None = None) -> str:
    # Mockup 01 style: left brand · right RS4L feel
    base = "RS TOURNEY BOT"
    if extra:
        return f"{base}  ·  {extra.upper() if len(extra) < 24 else extra}"
    return f"{base}  ·  ANNOUNCEMENT"


def footer_staff() -> str:
    return f"RS TOURNEY BOT  ·  STAFF  ·  {BOT_VERSION}"


def footer_player() -> str:
    return f"RS TOURNEY BOT  ·  SEASON 1  ·  {BOT_VERSION}"


def footer_rs4l(left: str = "RS TOURNEY BOT") -> str:
    return f"{left}                                          RS4L"


def base_embed(
    *,
    title: str,
    description: str | None = None,
    color: int | None = None,
    thumbnail: bool = True,
    author: str = "RHYTHM SYNDICATE · OFFICIAL",
) -> discord.Embed:
    """Embed chrome matching mockup 01: author line, red accent, logo thumb, RS footer."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else EMBED_COLOR,
    )
    if author:
        embed.set_author(name=author)
    if thumbnail and LOGO_PATH.is_file():
        embed.set_thumbnail(url=f"attachment://{LOGO_ATTACHMENT_NAME}")
    return embed


def pill_line(*chips: str) -> str:
    """Discord-friendly 'pill' row (mockup 01 chips)."""
    clean = [c.strip() for c in chips if c and str(c).strip()]
    if not clean:
        return ""
    return " · ".join(f"`{c}`" for c in clean)


def apply_logo_thumbnail(embed: discord.Embed) -> discord.Embed:
    if LOGO_PATH.is_file():
        embed.set_thumbnail(url=f"attachment://{LOGO_ATTACHMENT_NAME}")
    return embed


def logo_file() -> discord.File | None:
    if LOGO_PATH.is_file():
        return discord.File(LOGO_PATH, filename=LOGO_ATTACHMENT_NAME)
    return None


def files_for_embeds(*extras: discord.File | None) -> list[discord.File]:
    """Logo first (if present), then any extra image files (non-None)."""
    out: list[discord.File] = []
    logo = logo_file()
    if logo:
        out.append(logo)
    for f in extras:
        if f is not None:
            out.append(f)
    return out


def fmt_score(n: int | float | None) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def rank_prefix(rank: int) -> str:
    return RANK_MEDAL.get(rank, f"**{rank}.**")


def season_name(state: dict[str, Any]) -> str:
    return (state.get("season") or {}).get("name") or "Season 1"


def chip_line(*parts: str) -> str:
    clean = [p for p in parts if p]
    return " · ".join(clean)
