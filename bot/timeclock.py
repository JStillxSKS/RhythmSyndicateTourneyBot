"""
Season clock time source.

Production: real America/Los_Angeles wall clock.
Test mode: 1 real minute = N virtual hours (default 1 hour).

State keys under state["auto"]:
  test_real_origin_utc   — ISO when the scale started
  test_virtual_origin    — ISO virtual PT time at that moment
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import config
from config import RS_TZ

Anchor = Literal["before_open", "mid_week", "before_close"]


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def ensure_test_origins(
    state: dict[str, Any],
    *,
    anchor: Anchor = "before_open",
    real_now: datetime | None = None,
) -> None:
    """
    Set/reset test clock origins.
    before_open: virtual Sat 09:50 → open in ~10 real minutes at 1min=1hr
    mid_week: virtual Wednesday 12:00
    before_close: virtual Fri 23:50 → close in ~9 real minutes
    """
    real_now = real_now or datetime.now(timezone.utc)
    if real_now.tzinfo is None:
        real_now = real_now.replace(tzinfo=timezone.utc)

    # Fixed reference Saturday (any) — only weekday/time matter for window math
    # Use a known Saturday: 2026-07-18 is a Saturday
    base_sat = datetime(2026, 7, 18, 0, 0, 0, tzinfo=RS_TZ)
    if anchor == "before_open":
        virtual = base_sat.replace(hour=9, minute=50, second=0, microsecond=0)
    elif anchor == "before_close":
        # Friday of that week = July 24, 2026
        virtual = datetime(2026, 7, 24, 23, 50, 0, tzinfo=RS_TZ)
    else:  # mid_week
        virtual = datetime(2026, 7, 22, 12, 0, 0, tzinfo=RS_TZ)

    auto = state.setdefault("auto", {})
    auto["test_real_origin_utc"] = real_now.astimezone(timezone.utc).isoformat()
    auto["test_virtual_origin"] = virtual.isoformat()
    auto["test_anchor"] = anchor


def clock_now(state: dict[str, Any] | None = None, *, real_now: datetime | None = None) -> datetime:
    """
    Time used by the season scheduler (always returned in RS_TZ).
    """
    real_now = real_now or datetime.now(timezone.utc)
    if real_now.tzinfo is None:
        real_now = real_now.replace(tzinfo=timezone.utc)

    if not config.RS_TEST_TIME:
        return real_now.astimezone(RS_TZ)

    state = state or {}
    auto = state.get("auto") or {}
    real_origin = _parse_iso(auto.get("test_real_origin_utc"))
    virt_origin = _parse_iso(auto.get("test_virtual_origin"))
    if not real_origin or not virt_origin:
        # Lazy init: start just before Saturday open
        ensure_test_origins(state, anchor="before_open", real_now=real_now)
        auto = state.get("auto") or {}
        real_origin = _parse_iso(auto.get("test_real_origin_utc"))
        virt_origin = _parse_iso(auto.get("test_virtual_origin"))
        assert real_origin and virt_origin

    elapsed_real = (real_now.astimezone(timezone.utc) - real_origin.astimezone(timezone.utc)).total_seconds()
    # 1 real minute = RS_TEST_VHOURS_PER_RMIN virtual hours
    # virtual_seconds = real_seconds * (VHOURS_PER_RMIN * 3600 / 60)
    scale = float(config.RS_TEST_VHOURS_PER_RMIN) * 60.0  # default 1.0 * 60 = 60
    virtual_elapsed = elapsed_real * scale
    if virt_origin.tzinfo is None:
        virt_origin = virt_origin.replace(tzinfo=RS_TZ)
    virt = virt_origin.astimezone(RS_TZ) + timedelta(seconds=virtual_elapsed)
    return virt


def format_clock_status(state: dict[str, Any]) -> str:
    virt = clock_now(state)
    if not config.RS_TEST_TIME:
        return f"**Clock:** live PT · `{virt.strftime('%a %Y-%m-%d %H:%M %Z')}`"
    auto = state.get("auto") or {}
    return (
        f"**Clock:** TEST · **1 real min = {config.RS_TEST_VHOURS_PER_RMIN:g} virtual hr**\n"
        f"**Virtual now:** `{virt.strftime('%a %Y-%m-%d %H:%M %Z')}`\n"
        f"**Anchor:** `{auto.get('test_anchor') or '—'}` · "
        f"reset: `/rs season test-reset`"
    )
