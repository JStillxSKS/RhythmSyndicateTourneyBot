"""Env + constants for Rhythm Syndicate Tournament Bot."""
from __future__ import annotations

import os
from datetime import timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bump on every deploy-critical fix so /tourney help proves which build is live.
BOT_VERSION = "2026-07-16-golive-v1"

BOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BOT_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "rhythm-syndicate-logo.jpg"

DISCORD_TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()

_guild_raw = (os.getenv("RS_GUILD_ID") or "").strip()
RS_GUILD_ID = int(_guild_raw) if _guild_raw.isdigit() else None

_channel_raw = (os.getenv("RS_CHANNEL_ID") or "").strip()
RS_CHANNEL_ID = int(_channel_raw) if _channel_raw.isdigit() else None

_submit_raw = (os.getenv("RS_SUBMIT_CHANNEL_ID") or "").strip()
RS_SUBMIT_CHANNEL_ID = int(_submit_raw) if _submit_raw.isdigit() else RS_CHANNEL_ID

_role_raw = (os.getenv("RS_ADMIN_ROLE_IDS") or "").strip()
RS_ADMIN_ROLE_IDS: set[int] = set()
if _role_raw:
    for part in _role_raw.split(","):
        part = part.strip()
        if part.isdigit():
            RS_ADMIN_ROLE_IDS.add(int(part))

STATE_PATH = Path(os.getenv("RS_STATE_PATH") or PROJECT_DIR / "data" / "rs_state.json")

# Brand (from Rhythm Syndicate logo)
RS_RED = 0xE10600
RS_EMBED_COLOR = RS_RED

try:
    from zoneinfo import ZoneInfo

    RS_TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    # Windows without tzdata: fixed PST/PDT-agnostic UTC-8 fallback
    RS_TZ = timezone(timedelta(hours=-8), name="PST")

DIVISIONS = ("classic", "fusion", "arcade")
DIVISION_LABELS = {
    "classic": "Classic",
    "fusion": "Fusion",
    "arcade": "Arcade",
}

SEASON_WEEKS = 4
CAPTAIN_BURDEN_WEEK = 4
