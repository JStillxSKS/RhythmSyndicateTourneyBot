"""
PNG boards matching mockup quality:
  - Ops dashboard strip (mockup 04)
  - Division standings card (pin-worthy)
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config import ASSETS_DIR, CAPTAIN_BURDEN_WEEK, DIVISION_LABELS, DIVISIONS, LOGO_PATH

# Brand RGB (match render_banners)
RED = (225, 6, 0)
RED_SOFT = (255, 90, 80)
RED_DEEP = (90, 12, 14)
STEEL = (197, 204, 212)
STEEL_DIM = (120, 128, 138)
WHITE = (244, 246, 248)
BLACK = (10, 11, 14)
CARD = (22, 24, 28)
CARD2 = (28, 31, 36)
GREEN = (52, 211, 153)

OPS_STRIP_NAME = "rs-ops-strip.png"
DASH_STRIP_NAME = "rs-dashboard-strip.png"
SCORE_FLASH_NAME = "rs-score-flash.png"
TEAM_CARD_NAME = "rs-team-card.png"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates += [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\tahomabd.ttf",
        ]
    candidates += [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _load_logo(size: int) -> Image.Image | None:
    if not LOGO_PATH.is_file():
        return None
    im = Image.open(LOGO_PATH).convert("RGBA")
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _rounded(draw: ImageDraw.ImageDraw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def _chip(draw, xy, text, font, *, hot=False):
    x, y = xy
    pad_x, pad_y = 12, 6
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    w, h = tw + pad_x * 2, th + pad_y * 2
    fill = RED_DEEP if hot else (36, 40, 48)
    outline = RED if hot else (70, 76, 86)
    color = RED_SOFT if hot else STEEL
    _rounded(draw, (x, y, x + w, y + h), 8, fill, outline, 1)
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=color)
    return w, h


def render_ops_strip(
    *,
    week: int,
    season: str = "Season 1",
    status: str = "open",
    song: str | None = None,
    opens: str | None = None,
    closes: str | None = None,
    burden: bool = False,
) -> bytes:
    """Wide ops strip — **mockup 04 HTML** first, Pillow fallback."""
    try:
        from render_html import render_ops_mockup_png

        png = render_ops_mockup_png(
            week=week,
            season=season,
            status=status,
            song=song,
            opens=opens,
            closes=closes,
            burden=burden,
        )
        if png:
            return png
    except Exception as e:
        print(f"Mockup ops HTML path failed, Pillow fallback: {e}")

    w, h = 920, 220
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    # Header bar gradient-ish
    draw.rectangle((0, 0, w, 72), fill=(28, 12, 14))
    draw.rectangle((0, 70, w, 72), fill=RED)

    logo = _load_logo(48)
    if logo:
        img.paste(logo, (20, 12), logo)
        draw = ImageDraw.Draw(img)

    f_k = _font(12, True)
    f_title = _font(26, True)
    f_lab = _font(11, True)
    f_val = _font(16, True)
    f_chip = _font(12, True)
    f_foot = _font(11)

    draw.text((80, 14), f"RHYTHM SYNDICATE  ·  {season.upper()}", font=f_k, fill=STEEL_DIM)
    title = f"Week {week} scoring window"
    if burden:
        title = f"Week {week} · Captain's Burden"
    draw.text((80, 34), title, font=f_title, fill=WHITE)

    # Status pill top-right
    st = (status or "scheduled").lower()
    if st == "open":
        pill, hot = "● OPEN", True
    elif st == "closed":
        pill, hot = "● CLOSED", True
    else:
        pill, hot = "○ SCHEDULED", False
    bb = draw.textbbox((0, 0), pill, font=f_chip)
    pw = bb[2] - bb[0] + 28
    _chip(draw, (w - pw - 20, 20), pill, f_chip, hot=hot)

    # Three metric columns
    cols = [
        ("OPENS", opens or "—"),
        ("CLOSES", closes or "—"),
        ("SONG", (song or "TBD")[:36]),
    ]
    col_w = (w - 40) // 3
    y0 = 92
    for i, (lab, val) in enumerate(cols):
        x = 20 + i * col_w
        draw.text((x, y0), lab, font=f_lab, fill=STEEL_DIM)
        color = RED_SOFT if lab == "CLOSES" and st == "open" else WHITE
        draw.text((x, y0 + 22), val, font=f_val, fill=color)

    # Division chips + footer
    y_chip = 160
    x = 20
    for div in ("CLASSIC", "FUSION", "ARCADE"):
        cw, _ = _chip(draw, (x, y_chip), div, f_chip, hot=False)
        x += cw + 8
    if burden:
        _chip(draw, (x + 8, y_chip), "CAPTAIN + TEAMMATE × 2", f_chip, hot=True)

    draw.text(
        (w - 280, y_chip + 8),
        "Staff: /rs  ·  Players: /tourney",
        font=f_foot,
        fill=STEEL_DIM,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_standings_board(
    rows_by_div: dict[str, list[dict[str, Any]]],
    *,
    season: str = "Season 1",
    week: int = 1,
    title: str | None = None,
) -> bytes:
    """Three-column standings graphic (or single if one div has data focus)."""
    w, h = 960, 560
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    # Frame
    draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=16, outline=(48, 52, 60), width=2)
    draw.rectangle((12, 12, w - 12, 78), fill=(24, 14, 16))
    draw.rectangle((12, 76, w - 12, 78), fill=RED)

    logo = _load_logo(46)
    if logo:
        img.paste(logo, (28, 18), logo)
        draw = ImageDraw.Draw(img)

    f_k = _font(12, True)
    f_t = _font(24, True)
    f_h = _font(14, True)
    f_row = _font(13)
    f_score = _font(13, True)
    f_empty = _font(12)

    draw.text((88, 20), "RHYTHM SYNDICATE  ·  OFFICIAL", font=f_k, fill=STEEL_DIM)
    draw.text(
        (88, 40),
        title or f"{season} standings · through week {week}",
        font=f_t,
        fill=WHITE,
    )

    # Columns
    pad = 24
    col_gap = 14
    col_w = (w - pad * 2 - col_gap * 2) // 3
    y_top = 100

    for i, div in enumerate(DIVISIONS):
        x0 = pad + i * (col_w + col_gap)
        x1 = x0 + col_w
        _rounded(draw, (x0, y_top, x1, h - 28), 12, CARD, (48, 52, 60), 1)
        # Div header
        label = DIVISION_LABELS.get(div, div).upper()
        draw.rectangle((x0 + 1, y_top + 1, x1 - 1, y_top + 36), fill=CARD2)
        bb = draw.textbbox((0, 0), label, font=f_h)
        draw.text(
            (x0 + (col_w - (bb[2] - bb[0])) // 2, y_top + 10),
            label,
            font=f_h,
            fill=RED_SOFT if i == 0 else STEEL,
        )

        rows = rows_by_div.get(div) or []
        if not rows:
            draw.text((x0 + 16, y_top + 60), "No teams yet", font=f_empty, fill=STEEL_DIM)
            continue

        y = y_top + 48
        for r in rows[:10]:
            rank = int(r.get("rank") or 0)
            name = str(r.get("name") or "Team")[:18]
            total = int(r.get("total") or 0)
            # rank medal colors
            if rank == 1:
                rk_col = (255, 200, 60)
            elif rank == 2:
                rk_col = STEEL
            elif rank == 3:
                rk_col = (200, 140, 90)
            else:
                rk_col = STEEL_DIM
            draw.text((x0 + 12, y), f"{rank}.", font=f_score, fill=rk_col)
            draw.text((x0 + 36, y), name, font=f_row, fill=WHITE)
            sc = f"{total:,}"
            sb = draw.textbbox((0, 0), sc, font=f_score)
            draw.text((x1 - 14 - (sb[2] - sb[0]), y), sc, font=f_score, fill=STEEL)
            y += 28
            if y > h - 50:
                break

    draw.text((pad, h - 22), "Best verified  ·  missing teammate = 0  ·  /tourney standings", font=f_k, fill=STEEL_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_ops_from_state(state: dict[str, Any]) -> bytes:
    from datetime import datetime

    from config import RS_TZ
    from state import get_week

    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    song = week.get("song_title") or "TBD"
    if week.get("song_artist"):
        song = f"{song} — {week['song_artist']}"

    def fmt(iso: str | None) -> str:
        if not iso:
            return "—"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(RS_TZ)
            return dt.strftime("%a %I:%M %p %Z")
        except ValueError:
            return "—"

    return render_ops_strip(
        week=week_n,
        season=season.get("name") or "Season 1",
        status=week.get("status") or "scheduled",
        song=song,
        opens=fmt(week.get("open_at")),
        closes=fmt(week.get("close_at")),
        burden=week_n == CAPTAIN_BURDEN_WEEK,
    )


def render_standings_from_state(state: dict[str, Any], division: str | None = None) -> bytes:
    from rules import standings_rows

    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    teams = state.get("teams") or []
    subs = state.get("submissions") or []
    divs = [division] if division and division in DIVISIONS else list(DIVISIONS)
    rows_by: dict[str, list] = {}
    for d in DIVISIONS:
        if d in divs:
            rows_by[d] = standings_rows(teams, subs, d, through_week=week_n)
        else:
            rows_by[d] = []
    return render_standings_board(
        rows_by,
        season=season.get("name") or "Season 1",
        week=week_n,
    )


def render_score_flash(
    *,
    score: int,
    verified: bool = True,
    week: int = 1,
    player: str | None = None,
    team: str | None = None,
    mode_note: str | None = None,
) -> bytes:
    """Compact score verified / pending card for intake replies."""
    w, h = 720, 280
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=16, outline=(48, 52, 60), width=2)
    # Left accent bar
    bar = RED if verified else STEEL_DIM
    draw.rectangle((12, 12, 18, h - 12), fill=bar)

    logo = _load_logo(56)
    if logo:
        img.paste(logo, (36, 28), logo)
        draw = ImageDraw.Draw(img)

    f_k = _font(12, True)
    f_t = _font(22, True)
    f_score = _font(48, True)
    f_sub = _font(14)
    f_chip = _font(12, True)

    draw.text((110, 30), "RHYTHM SYNDICATE  ·  SCORE INTAKE", font=f_k, fill=STEEL_DIM)
    title = "SCORE VERIFIED" if verified else "SCORE PENDING"
    draw.text((110, 52), title, font=f_t, fill=WHITE if verified else STEEL)

    sc = f"{int(score):,}"
    draw.text((36, 110), sc, font=f_score, fill=RED_SOFT if verified else STEEL)

    bits = [f"WEEK {week}"]
    if team:
        bits.append(team[:24].upper())
    if player:
        bits.append(player[:20])
    draw.text((36, 180), "  ·  ".join(bits), font=f_sub, fill=STEEL_DIM)

    pill = "COUNTS" if verified else "AWAITING STAFF"
    _chip(draw, (w - 160, 120), pill, f_chip, hot=verified)

    if mode_note:
        draw.text((36, 220), mode_note[:70], font=f_sub, fill=(255, 160, 100))
    else:
        draw.text(
            (36, 220),
            "Best verified only  ·  /tourney my-score",
            font=f_sub,
            fill=STEEL_DIM,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_team_card(
    *,
    name: str,
    division: str,
    captain_score: int,
    teammate_score: int,
    team_total: int,
    week: int = 1,
    burden: bool = False,
    season_total: int | None = None,
) -> bytes:
    """Team card for /tourney my-team."""
    w, h = 720, 320
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=16, outline=(48, 52, 60), width=2)
    draw.rectangle((12, 12, w - 12, 78), fill=(24, 14, 16))
    draw.rectangle((12, 76, w - 12, 78), fill=RED)

    logo = _load_logo(48)
    if logo:
        img.paste(logo, (28, 18), logo)
        draw = ImageDraw.Draw(img)

    f_k = _font(12, True)
    f_t = _font(24, True)
    f_lab = _font(11, True)
    f_val = _font(20, True)
    f_big = _font(36, True)
    f_chip = _font(12, True)

    draw.text((90, 20), "RHYTHM SYNDICATE  ·  TEAM", font=f_k, fill=STEEL_DIM)
    draw.text((90, 40), (name or "Team")[:28], font=f_t, fill=WHITE)

    div = (division or "").upper() or "—"
    _chip(draw, (w - 140, 24), div[:12], f_chip, hot=True)

    # Two columns captain / teammate
    draw.text((36, 100), "CAPTAIN", font=f_lab, fill=STEEL_DIM)
    draw.text((36, 120), f"{int(captain_score):,}", font=f_val, fill=WHITE)
    draw.text((280, 100), "TEAMMATE", font=f_lab, fill=STEEL_DIM)
    draw.text((280, 120), f"{int(teammate_score):,}", font=f_val, fill=WHITE)

    draw.text((36, 170), f"WEEK {week} TEAM TOTAL", font=f_lab, fill=STEEL_DIM)
    draw.text((36, 190), f"{int(team_total):,}", font=f_big, fill=RED_SOFT)

    if burden:
        _chip(draw, (320, 200), "CAPTAIN'S BURDEN", f_chip, hot=True)

    if season_total is not None:
        draw.text((36, 260), f"SEASON TOTAL  {int(season_total):,}", font=f_val, fill=STEEL)
    else:
        draw.text((36, 260), "Best verified  ·  missing = 0", font=f_lab, fill=STEEL_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def board_discord_file(png_bytes: bytes, filename: str) -> Any:
    import discord

    return discord.File(io.BytesIO(png_bytes), filename=filename)


def write_board_previews() -> list[Path]:
    """Dev: write sample boards under assets/mockups/live-boards/."""
    out_dir = ASSETS_DIR / "mockups" / "live-boards"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        "classic": [
            {"rank": 1, "name": "PulseCore", "total": 1890000},
            {"rank": 2, "name": "Steel Sticks", "total": 950000},
        ],
        "fusion": [{"rank": 1, "name": "Neon Pair", "total": 1200000}],
        "arcade": [],
    }
    paths = []
    p1 = out_dir / "ops-strip-preview.png"
    p1.write_bytes(
        render_ops_strip(
            week=2,
            status="open",
            song="Paranoid — Black Sabbath",
            opens="Sat 10:00 AM PST",
            closes="Fri 11:59 PM PST",
        )
    )
    paths.append(p1)
    p2 = out_dir / "standings-preview.png"
    p2.write_bytes(render_standings_board(sample, week=2))
    paths.append(p2)
    p3 = out_dir / "score-flash-preview.png"
    p3.write_bytes(
        render_score_flash(score=985_420, verified=True, week=1, player="PulseMaster", team="PulseCore")
    )
    paths.append(p3)
    p4 = out_dir / "team-card-preview.png"
    p4.write_bytes(
        render_team_card(
            name="PulseCore",
            division="classic",
            captain_score=985_420,
            teammate_score=910_000,
            team_total=1_895_420,
            week=1,
            season_total=1_895_420,
        )
    )
    paths.append(p4)
    return paths
