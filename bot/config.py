"""Env + constants for Rhythm Syndicate Tournament Bot."""
from __future__ import annotations

import os
from datetime import timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bump on every deploy-critical fix so /tourney help proves which build is live.
BOT_VERSION = "2026-07-18-fusion-both-captains-v1"

# Automation (env: "0"/"false"/"off" to disable)
def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


RS_AUTO_WEEK = _env_bool("RS_AUTO_WEEK", True)
RS_AUTO_ANNOUNCE = _env_bool("RS_AUTO_ANNOUNCE", True)
RS_AUTO_DIGEST = _env_bool("RS_AUTO_DIGEST", True)
RS_BOARD_THROTTLE_SEC = int(os.getenv("RS_BOARD_THROTTLE_SEC") or "45")

# Test time: 1 real minute = RS_TEST_VHOURS_PER_RMIN virtual hours (default 1)
RS_TEST_TIME = _env_bool("RS_TEST_TIME", False)
try:
    RS_TEST_VHOURS_PER_RMIN = float(os.getenv("RS_TEST_VHOURS_PER_RMIN") or "1")
except ValueError:
    RS_TEST_VHOURS_PER_RMIN = 1.0

# Tick: faster when test time is on
_default_tick = "10" if RS_TEST_TIME else "45"
RS_SCHEDULER_TICK_SEC = int(os.getenv("RS_SCHEDULER_TICK_SEC") or _default_tick)

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
