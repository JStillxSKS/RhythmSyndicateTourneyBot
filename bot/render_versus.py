"""
Versus / verse cards — teams of 2, highest score wins.

Policy (user lock):
  • daily  → mockup 03 HUD score duel
  • big moments → fight / ring / poster / result (killscreen) / title
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFilter

from config import ASSETS_DIR, CAPTAIN_BURDEN_WEEK, DIVISION_LABELS
from render_banners import (
    BLACK,
    RED,
    STEEL,
    STEEL_DIM,
    WHITE,
    _font,
    _load_logo,
    _rounded_rect,
    _text_center,
)
from theme import VERSE_ATTACHMENT_NAME

VerseStyle = Literal["daily", "fight", "ring", "poster", "result", "title"]

DAILY_STYLE: VerseStyle = "daily"
BIG_MOMENT_STYLES: tuple[VerseStyle, ...] = ("fight", "ring", "poster", "result", "title")

STYLE_LABELS = {
    "daily": "Daily HUD",
    "fight": "Classic fight card",
    "ring": "Drum battle ring",
    "poster": "Concert poster",
    "result": "Result killscreen",
    "title": "Title match",
}


@dataclass
class VerseSide:
    name: str
    captain: str
    teammate: str
    score: int
    division: str = ""
    seed: int | None = None


@dataclass
class VerseMatchup:
    side_a: VerseSide
    side_b: VerseSide
    week: int = 1
    season: str = "Season 1"
    window_open: bool = True
    burden: bool = False
    subtitle: str | None = None  # e.g. "Highest verified score"


def _clip(draw: ImageDraw.ImageDraw, text: str, font: Any, max_w: int) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    t = text
    while len(t) > 1 and draw.textbbox((0, 0), t + "…", font=font)[2] > max_w:
        t = t[:-1]
    return t + "…"


def _fmt(n: int) -> str:
    return f"{int(n):,}"


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _lead_delta(a: int, b: int) -> tuple[str, str, bool]:
    """Returns (a_line, b_line, a_is_ahead)."""
    if a == b:
        return ("● tied", "● tied", False)
    if a > b:
        d = a - b
        return (f"▲ +{_fmt(d)} lead", "▼ chasing", True)
    d = b - a
    return ("▼ chasing", f"▲ +{_fmt(d)} lead", False)


# ---------------------------------------------------------------------------
# 03 DAILY HUD
# ---------------------------------------------------------------------------

def render_daily_hud(m: VerseMatchup) -> bytes:
    w, h = 960, 380
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle((0, 0, w, 56), fill=(14, 17, 22))
    draw.rectangle((0, 55, w, 56), fill=(37, 43, 51))
    # red wash
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rectangle((0, 0, w // 2, 56), fill=(*RED, 40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    logo = _load_logo(36)
    if logo:
        img.paste(logo, (16, 10), logo)
        draw = ImageDraw.Draw(img)

    font_h = _font(14, bold=True)
    font_sm = _font(12, bold=True)
    draw.text((64, 18), "RHYTHM SYNDICATE", font=font_h, fill=WHITE)
    draw.text((64, 34), f"{m.season.upper()}  ·  VERSE", font=_font(11), fill=STEEL_DIM)

    # live badge
    badge = "● LIVE SCORE" if m.window_open else "● FINAL"
    bb = draw.textbbox((0, 0), badge, font=font_sm)
    bw = bb[2] - bb[0] + 20
    bx = w - 16 - bw
    _rounded_rect(draw, (bx, 14, bx + bw, 42), 5, (50, 12, 12), RED, 1)
    draw.text((bx + 10, 20), badge, font=font_sm, fill=(255, 138, 132))

    a, b = m.side_a, m.side_b
    a_lead, b_lead, a_ahead = _lead_delta(a.score, b.score)

    # Panels
    def panel(x0: int, x1: int, side: VerseSide, hot: bool, delta: str) -> None:
        y0, y1 = 72, 300
        fill = (26, 16, 16) if hot else (18, 22, 28)
        outline = (*RED, ) if hot else (42, 49, 58)
        # outline RGB only
        ol = RED if hot else (42, 49, 58)
        _rounded_rect(draw, (x0, y0, x1, y1), 12, fill, ol, 2 if hot else 1)
        if hot:
            # soft glow left edge
            draw.rectangle((x0, y0 + 8, x0 + 4, y1 - 8), fill=RED)

        font_name = _font(26, bold=True)
        name = _clip(draw, side.name.upper(), font_name, x1 - x0 - 36)
        color = (255, 107, 99) if hot else WHITE
        draw.text((x0 + 18, y0 + 16), name, font=font_name, fill=color)

        duo = f"Captain {side.captain}  ·  Teammate {side.teammate}"
        duo = _clip(draw, duo, _font(13), x1 - x0 - 36)
        draw.text((x0 + 18, y0 + 52), duo, font=_font(13), fill=STEEL_DIM)

        draw.text((x0 + 18, y0 + 100), "TEAM TOTAL", font=_font(11, bold=True), fill=STEEL_DIM)
        sc_color = RED if hot else WHITE
        draw.text((x0 + 18, y0 + 118), _fmt(side.score), font=_font(42, bold=True), fill=sc_color)

        dcol = (93, 202, 138) if "lead" in delta or "tied" in delta else (255, 107, 99)
        if "tied" in delta:
            dcol = STEEL
        draw.text((x0 + 18, y0 + 180), delta, font=_font(13, bold=True), fill=dcol)

    panel(16, 430, a, a_ahead or a.score >= b.score, a_lead)
    panel(530, 944, b, (not a_ahead) and b.score > a.score, b_lead)

    # VS pill
    cx, cy = w // 2, 186
    r = 34
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED)
    draw.ellipse((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), outline=(120, 20, 15), width=2)
    _text_center(draw, (cx, cy), "VS", _font(18, bold=True), WHITE)

    # Footer
    draw.rectangle((0, 320, w, h), fill=(12, 15, 20))
    draw.line((0, 320, w, 320), fill=(37, 43, 51), width=1)
    div = DIVISION_LABELS.get(a.division, a.division) or DIVISION_LABELS.get(b.division, b.division) or "—"
    status = "WINDOW OPEN" if m.window_open else "WINDOW CLOSED"
    foot = f"{'● ' if m.window_open else ''}{status}   ·   {div.upper()}   ·   WEEK {m.week}"
    if m.burden:
        foot += "   ·   CAPTAIN'S BURDEN"
    foot += "   ·   BEST VERIFIED ONLY"
    draw.text((18, 338), foot, font=_font(11, bold=True), fill=STEEL_DIM if not m.window_open else (93, 202, 138))
    draw.text((w - 150, 338), "RS TOURNEY BOT", font=_font(11, bold=True), fill=STEEL_DIM)

    return _png(img)


# ---------------------------------------------------------------------------
# 01 CLASSIC FIGHT
# ---------------------------------------------------------------------------

def render_fight_card(m: VerseMatchup) -> bytes:
    w, h = 960, 500
    img = Image.new("RGB", (w, h), BLACK)
    # glows
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-80, 40, 360, 460), fill=(*RED, 50))
    gd.ellipse((w - 360, 40, w + 80, 460), fill=(*STEEL, 28))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=16, outline=(42, 48, 56), width=2)
    # corners
    for pts in (
        [(18, 50), (18, 18), (50, 18)],
        [(w - 50, 18), (w - 18, 18), (w - 18, 50)],
        [(18, h - 50), (18, h - 18), (50, h - 18)],
        [(w - 50, h - 18), (w - 18, h - 18), (w - 18, h - 50)],
    ):
        col = RED if pts[0][0] < w // 2 else STEEL_DIM
        draw.line(pts, fill=col, width=3)

    a, b = m.side_a, m.side_b
    font_team = _font(36, bold=True)
    font_lab = _font(11, bold=True)

    # Left
    draw.text((40, 48), (DIVISION_LABELS.get(a.division, a.division) or "DIVISION").upper(), font=font_lab, fill=STEEL_DIM)
    name_a = _clip(draw, a.name.upper(), font_team, 320)
    # multi-line if long
    draw.text((40, 72), name_a, font=font_team, fill=WHITE)
    draw.text((40, 150), "CAPTAIN", font=font_lab, fill=RED)
    draw.text((40, 168), _clip(draw, a.captain, _font(16), 300), font=_font(16), fill=(200, 205, 212))
    draw.text((40, 200), "TEAMMATE", font=font_lab, fill=RED)
    draw.text((40, 218), _clip(draw, a.teammate, _font(16), 300), font=_font(16), fill=(200, 205, 212))
    draw.text((40, 280), "TEAM SCORE", font=font_lab, fill=STEEL_DIM)
    draw.text((40, 300), _fmt(a.score), font=_font(44, bold=True), fill=RED)

    # Right
    div_b = (DIVISION_LABELS.get(b.division, b.division) or "DIVISION").upper()
    bb = draw.textbbox((0, 0), div_b, font=font_lab)
    draw.text((w - 40 - (bb[2] - bb[0]), 48), div_b, font=font_lab, fill=STEEL_DIM)
    name_b = _clip(draw, b.name.upper(), font_team, 320)
    bb = draw.textbbox((0, 0), name_b, font=font_team)
    draw.text((w - 40 - (bb[2] - bb[0]), 72), name_b, font=font_team, fill=STEEL)
    for label, val, y in (("CAPTAIN", b.captain, 150), ("TEAMMATE", b.teammate, 200)):
        bb = draw.textbbox((0, 0), label, font=font_lab)
        draw.text((w - 40 - (bb[2] - bb[0]), y), label, font=font_lab, fill=STEEL)
        vv = _clip(draw, val, _font(16), 300)
        bb = draw.textbbox((0, 0), vv, font=_font(16))
        draw.text((w - 40 - (bb[2] - bb[0]), y + 18), vv, font=_font(16), fill=(200, 205, 212))
    lab = "TEAM SCORE"
    bb = draw.textbbox((0, 0), lab, font=font_lab)
    draw.text((w - 40 - (bb[2] - bb[0]), 280), lab, font=font_lab, fill=STEEL_DIM)
    sc = _fmt(b.score)
    bb = draw.textbbox((0, 0), sc, font=_font(44, bold=True))
    draw.text((w - 40 - (bb[2] - bb[0]), 300), sc, font=_font(44, bold=True), fill=STEEL)

    # Center
    logo = _load_logo(78)
    if logo:
        img.paste(logo, (w // 2 - 39, 90), logo)
        draw = ImageDraw.Draw(img)
    _text_center(draw, (w // 2, 220), "V", _font(48, bold=True), WHITE)
    # draw VS with red S
    vs_font = _font(48, bold=True)
    v = "V"
    s = "S"
    vb = draw.textbbox((0, 0), v, font=vs_font)
    sb = draw.textbbox((0, 0), s, font=vs_font)
    tw = (vb[2] - vb[0]) + (sb[2] - sb[0])
    x0 = w // 2 - tw // 2
    draw.text((x0, 195), v, font=vs_font, fill=WHITE)
    draw.text((x0 + (vb[2] - vb[0]), 195), s, font=vs_font, fill=RED)
    _text_center(draw, (w // 2, 270), f"WEEK {m.week}  ·  HEAD-TO-HEAD", _font(11, bold=True), STEEL_DIM)
    _text_center(draw, (w // 2, 292), "HIGHEST VERIFIED SCORE", _font(11, bold=True), STEEL_DIM)
    if m.burden:
        _text_center(draw, (w // 2, 314), "CAPTAIN'S BURDEN", _font(12, bold=True), RED)

    draw.rectangle((10, h - 16, w - 10, h - 10), fill=None)
    draw.line((24, h - 14, w - 24, h - 14), fill=RED, width=3)

    return _png(img)


# ---------------------------------------------------------------------------
# 02 RING
# ---------------------------------------------------------------------------

def render_ring(m: VerseMatchup) -> bytes:
    w, h = 720, 720
    img = Image.new("RGB", (w, h), BLACK)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((80, 100, w - 80, h - 80), fill=(*RED, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    logo = _load_logo(48)
    if logo:
        img.paste(logo, (28, 24), logo)
        draw = ImageDraw.Draw(img)
    draw.text((w - 28 - 140, 28), "VERSE CARD", font=_font(12, bold=True), fill=RED)
    div = DIVISION_LABELS.get(m.side_a.division, m.side_a.division) or ""
    draw.text((w - 28 - 140, 48), f"{div.upper()}  ·  WEEK {m.week}", font=_font(11), fill=STEEL_DIM)

    cx, cy = w // 2, h // 2 + 10
    draw.ellipse((cx - 250, cy - 250, cx + 250, cy + 250), outline=STEEL_DIM, width=2)
    # dashed middle ring
    for i in range(0, 360, 10):
        if (i // 10) % 2 == 0:
            draw.arc((cx - 210, cy - 210, cx + 210, cy + 210), start=i, end=i + 6, fill=RED, width=2)
    draw.ellipse((cx - 160, cy - 160, cx + 160, cy + 160), outline=(42, 48, 56), width=1)

    a, b = m.side_a, m.side_b
    # top team
    _text_center(draw, (cx, cy - 180), _clip(draw, a.name.upper(), _font(24, bold=True), 360), _font(24, bold=True), RED)
    _text_center(draw, (cx, cy - 148), f"C · {a.captain}  ·  T · {a.teammate}", _font(13), STEEL_DIM)
    _text_center(draw, (cx, cy - 110), _fmt(a.score), _font(32, bold=True), WHITE)

    _text_center(draw, (cx, cy - 8), "VS", _font(52, bold=True), RED)
    _text_center(draw, (cx, cy + 36), "DRUM BATTLE", _font(12, bold=True), STEEL_DIM)

    _text_center(draw, (cx, cy + 120), _clip(draw, b.name.upper(), _font(24, bold=True), 360), _font(24, bold=True), STEEL)
    _text_center(draw, (cx, cy + 152), f"C · {b.captain}  ·  T · {b.teammate}", _font(13), STEEL_DIM)
    _text_center(draw, (cx, cy + 190), _fmt(b.score), _font(32, bold=True), WHITE)

    _text_center(draw, (cx, h - 36), "HIGHEST SCORE WINS  ·  RS4L", _font(12, bold=True), STEEL_DIM)
    return _png(img)


# ---------------------------------------------------------------------------
# 04 POSTER
# ---------------------------------------------------------------------------

def render_poster(m: VerseMatchup) -> bytes:
    w, h = 480, 760
    img = Image.new("RGB", (w, h), BLACK)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((40, -40, w - 40, 320), fill=(*RED, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    logo = _load_logo(110)
    if logo:
        img.paste(logo, (w // 2 - 55, 36), logo)
        draw = ImageDraw.Draw(img)

    _text_center(draw, (w // 2, 170), "ONE NIGHT ONLY  ·  SEASON 1", _font(11, bold=True), STEEL)
    _text_center(draw, (w // 2, 210), "DRUM VERSE", _font(28, bold=True), WHITE)
    _text_center(draw, (w // 2, 248), "SHOWDOWN", _font(34, bold=True), RED)

    # rule
    draw.line((80, 280, w - 80, 280), fill=RED, width=2)

    a, b = m.side_a, m.side_b
    _text_center(draw, (w // 2, 330), _clip(draw, a.name.upper(), _font(28, bold=True), 400), _font(28, bold=True), RED)
    _text_center(draw, (w // 2, 365), f"Captain {a.captain}  ·  Teammate {a.teammate}", _font(13), STEEL_DIM)
    _text_center(draw, (w // 2, 405), _fmt(a.score), _font(36, bold=True), WHITE)

    _text_center(draw, (w // 2, 460), "VS", _font(28, bold=True), WHITE)

    _text_center(draw, (w // 2, 520), _clip(draw, b.name.upper(), _font(28, bold=True), 400), _font(28, bold=True), STEEL)
    _text_center(draw, (w // 2, 555), f"Captain {b.captain}  ·  Teammate {b.teammate}", _font(13), STEEL_DIM)
    _text_center(draw, (w // 2, 595), _fmt(b.score), _font(36, bold=True), WHITE)

    div = DIVISION_LABELS.get(a.division, a.division) or "DIVISION"
    _text_center(draw, (w // 2, 660), f"{div.upper()}  ·  WEEK {m.week}", _font(12, bold=True), WHITE)
    _text_center(draw, (w // 2, 688), "Teams of 2  ·  Highest verified score wins", _font(12), STEEL_DIM)
    _text_center(draw, (w // 2, 720), "RS4L", _font(14, bold=True), RED)
    return _png(img)


# ---------------------------------------------------------------------------
# 05 RESULT KILLSCREEN
# ---------------------------------------------------------------------------

def render_result(m: VerseMatchup) -> bytes:
    w, h = 960, 440
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img)

    a, b = m.side_a, m.side_b
    a_wins = a.score >= b.score

    # halves
    draw.rectangle((0, 0, w // 2, h), fill=(16, 8, 8))
    draw.rectangle((w // 2, 0, w, h), fill=(10, 12, 16))
    # red wash left
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.polygon([(0, 0), (w // 2 + 40, 0), (w // 2 - 40, h), (0, h)], fill=(*RED, 45))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # slash
    draw.line([(w // 2 + 20, 0), (w // 2 - 20, h)], fill=RED, width=5)

    # VS badge
    vs_box = (w // 2 - 36, h // 2 - 36, w // 2 + 36, h // 2 + 36)
    # rotated look: draw diamond-ish rounded rect
    _rounded_rect(draw, vs_box, 12, BLACK, RED, 3)
    _text_center(draw, (w // 2, h // 2), "VS", _font(18, bold=True), WHITE)

    # winner badge
    win_side = a if a_wins else b
    if a_wins:
        _rounded_rect(draw, (28, 20, 120, 44), 5, (60, 15, 15), RED, 1)
        draw.text((40, 24), "WINNER", font=_font(12, bold=True), fill=(255, 138, 132))
    else:
        _rounded_rect(draw, (w - 120, 20, w - 28, 44), 5, (60, 15, 15), RED, 1)
        draw.text((w - 108, 24), "WINNER", font=_font(12, bold=True), fill=(255, 138, 132))

    # left content
    draw.text((36, 70), "HOME SIDE", font=_font(11, bold=True), fill=(255, 138, 132) if a_wins else STEEL_DIM)
    draw.text((36, 100), _clip(draw, a.name.upper(), _font(36, bold=True), 380), font=_font(36, bold=True), fill=WHITE)
    draw.text((36, 190), f"C  {a.captain}", font=_font(14), fill=STEEL_DIM)
    draw.text((36, 214), f"T  {a.teammate}", font=_font(14), fill=STEEL_DIM)
    draw.text((36, 280), _fmt(a.score), font=_font(44, bold=True), fill=RED if a_wins else WHITE)

    # right content
    rb = "AWAY SIDE"
    bb = draw.textbbox((0, 0), rb, font=_font(11, bold=True))
    draw.text((w - 36 - (bb[2] - bb[0]), 70), rb, font=_font(11, bold=True), fill=STEEL_DIM)
    name = _clip(draw, b.name.upper(), _font(36, bold=True), 380)
    bb = draw.textbbox((0, 0), name, font=_font(36, bold=True))
    draw.text((w - 36 - (bb[2] - bb[0]), 100), name, font=_font(36, bold=True), fill=WHITE)
    for i, line in enumerate((f"C  {b.captain}", f"T  {b.teammate}")):
        bb = draw.textbbox((0, 0), line, font=_font(14))
        draw.text((w - 36 - (bb[2] - bb[0]), 190 + i * 24), line, font=_font(14), fill=STEEL_DIM)
    sc = _fmt(b.score)
    bb = draw.textbbox((0, 0), sc, font=_font(44, bold=True))
    draw.text((w - 36 - (bb[2] - bb[0]), 280), sc, font=_font(44, bold=True), fill=RED if not a_wins else STEEL)

    logo = _load_logo(40)
    if logo:
        img.paste(logo, (w // 2 - 20, h - 52), logo)

    _ = win_side  # silence lint
    return _png(img)


# ---------------------------------------------------------------------------
# 06 TITLE MATCH
# ---------------------------------------------------------------------------

def render_title(m: VerseMatchup) -> bytes:
    w, h = 960, 520
    img = Image.new("RGB", (w, h), BLACK)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((80, -120, w - 80, 200), fill=(*RED, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(45))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    logo = _load_logo(52)
    if logo:
        img.paste(logo, (28, 22), logo)
        draw = ImageDraw.Draw(img)
    draw.text((92, 28), "RHYTHM SYNDICATE", font=_font(11, bold=True), fill=STEEL_DIM)
    draw.text((92, 46), f"{m.season.upper()}  ·  OFFICIAL VERSE", font=_font(15, bold=True), fill=WHITE)

    _rounded_rect(draw, (w - 150, 28, w - 28, 58), 6, RED, None, 0)
    draw.text((w - 138, 34), "TITLE MATCH", font=_font(12, bold=True), fill=WHITE)

    _text_center(draw, (w // 2, 100), m.subtitle or "DIVISION CROWN ON THE LINE", _font(12, bold=True), STEEL)
    title = "CAPTAIN'S BURDEN  FINALE" if m.burden else f"WEEK {m.week}  TITLE VERSE"
    # split last word red if burden
    if m.burden:
        _text_center(draw, (w // 2, 140), "CAPTAIN'S BURDEN", _font(34, bold=True), WHITE)
        _text_center(draw, (w // 2, 180), "FINALE", _font(34, bold=True), RED)
    else:
        _text_center(draw, (w // 2, 150), title, _font(32, bold=True), WHITE)

    a, b = m.side_a, m.side_b

    def box(x0: int, x1: int, side: VerseSide, hot: bool) -> None:
        y0, y1 = 220, 430
        ol = RED if hot else (44, 51, 60)
        _rounded_rect(draw, (x0, y0, x1, y1), 12, (16, 18, 22), ol, 2 if hot else 1)
        seed = f"#{side.seed} SEED" if side.seed else "TEAM"
        div = DIVISION_LABELS.get(side.division, side.division) or ""
        draw.text((x0 + 18, y0 + 16), f"{seed}  ·  {div.upper()}", font=_font(11, bold=True), fill=STEEL_DIM)
        draw.text(
            (x0 + 18, y0 + 40),
            _clip(draw, side.name.upper(), _font(26, bold=True), x1 - x0 - 36),
            font=_font(26, bold=True),
            fill=RED if hot else WHITE,
        )
        # rows
        for i, (lab, val) in enumerate(
            (
                ("CAPTAIN", side.captain),
                ("TEAMMATE ×2" if m.burden else "TEAMMATE", side.teammate),
            )
        ):
            yy = y0 + 90 + i * 40
            _rounded_rect(draw, (x0 + 16, yy, x1 - 16, yy + 32), 6, (12, 14, 18), None, 0)
            draw.text((x0 + 28, yy + 8), lab, font=_font(10, bold=True), fill=STEEL_DIM)
            vv = _clip(draw, val, _font(13), 160)
            bb = draw.textbbox((0, 0), vv, font=_font(13))
            draw.text((x1 - 28 - (bb[2] - bb[0]), yy + 8), vv, font=_font(13), fill=WHITE)
        lab = "BURDEN TOTAL" if m.burden else "TEAM TOTAL"
        draw.text((x0 + 18, y1 - 70), lab, font=_font(10, bold=True), fill=STEEL_DIM)
        draw.text((x0 + 18, y1 - 50), _fmt(side.score), font=_font(32, bold=True), fill=RED if hot else WHITE)

    a_hot = a.score >= b.score
    box(28, 400, a, a_hot)
    box(560, 932, b, not a_hot and b.score > a.score)

    _text_center(draw, (w // 2, 300), "VS", _font(32, bold=True), WHITE)
    _text_center(draw, (w // 2, 340), f"WEEK {m.week}", _font(12, bold=True), STEEL_DIM)

    # chips
    chips = ["HIGHEST SCORE WINS", "BEST VERIFIED ONLY", "RS4L"]
    if m.burden:
        chips.insert(0, "CAPTAIN + TEAMMATE × 2")
    font_c = _font(11, bold=True)
    widths = []
    for c in chips:
        bb = draw.textbbox((0, 0), c, font=font_c)
        widths.append(bb[2] - bb[0] + 24)
    total = sum(widths) + 10 * (len(chips) - 1)
    x = w // 2 - total // 2
    y = 460
    for c, cw in zip(chips, widths):
        hot = "CAPTAIN" in c or c == "RS4L"
        _rounded_rect(draw, (x, y, x + cw, y + 28), 14, (30, 12, 12) if hot else (21, 26, 33), RED if hot else (44, 51, 60), 1)
        draw.text((x + 12, y + 7), c, font=font_c, fill=(255, 138, 132) if hot else STEEL)
        x += cw + 10

    return _png(img)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_verse(m: VerseMatchup, style: VerseStyle = "daily") -> bytes:
    style = style if style in STYLE_LABELS else "daily"
    if style == "daily":
        return render_daily_hud(m)
    if style == "fight":
        return render_fight_card(m)
    if style == "ring":
        return render_ring(m)
    if style == "poster":
        return render_poster(m)
    if style == "result":
        return render_result(m)
    if style == "title":
        return render_title(m)
    return render_daily_hud(m)


def verse_discord_file(png: bytes, filename: str = VERSE_ATTACHMENT_NAME):
    import discord

    return discord.File(io.BytesIO(png), filename=filename)


def matchup_from_teams(
    state: dict[str, Any],
    team_a: dict[str, Any],
    team_b: dict[str, Any],
    *,
    week: int | None = None,
    name_a: tuple[str, str] | None = None,
    name_b: tuple[str, str] | None = None,
) -> VerseMatchup:
    """Build matchup from team dicts + optional (captain_display, teammate_display)."""
    from rules import team_week_breakdown
    from state import get_week

    season = state.get("season") or {}
    week_n = int(week if week is not None else season.get("current_week") or 1)
    subs = state.get("submissions") or []
    w = get_week(state, week_n)
    burden = week_n == CAPTAIN_BURDEN_WEEK

    def side(team: dict[str, Any], names: tuple[str, str] | None) -> VerseSide:
        bd = team_week_breakdown(
            subs, team.get("captain_user_id"), team.get("teammate_user_id"), week_n
        )
        cap_n, mate_n = names if names else ("Captain", "Teammate")
        return VerseSide(
            name=str(team.get("name") or "Team"),
            captain=cap_n,
            teammate=mate_n,
            score=int(bd["team_total"]),
            division=str(team.get("division") or ""),
        )

    return VerseMatchup(
        side_a=side(team_a, name_a),
        side_b=side(team_b, name_b),
        week=week_n,
        season=str(season.get("name") or "Season 1"),
        window_open=(w.get("status") or "") == "open",
        burden=burden,
        subtitle="Highest verified score" if not burden else "Captain + Teammate × 2",
    )


def write_previews(out_dir: Any = None) -> list[Any]:
    """Dev: write all styles with sample data."""
    from pathlib import Path

    out = Path(out_dir) if out_dir else ASSETS_DIR / "mockups" / "versus" / "live"
    out.mkdir(parents=True, exist_ok=True)
    m = VerseMatchup(
        side_a=VerseSide("Arcade Rats", "Nova", "Pixel", 1_455_900, "arcade", seed=1),
        side_b=VerseSide("Coin Feed", "Zig", "Buffer", 1_427_500, "arcade", seed=2),
        week=1,
        window_open=True,
    )
    paths = []
    for style in ("daily", "fight", "ring", "poster", "result", "title"):
        if style == "title":
            m2 = VerseMatchup(
                side_a=VerseSide("Hex Grid", "Vex", "Glyph", 2_640_000, "fusion", seed=1),
                side_b=VerseSide("Phase Lock", "Orbit", "Drift", 2_510_200, "fusion", seed=2),
                week=4,
                burden=True,
                window_open=False,
            )
            data = render_verse(m2, style)  # type: ignore[arg-type]
        else:
            data = render_verse(m, style)  # type: ignore[arg-type]
        p = out / f"verse-{style}.png"
        p.write_bytes(data)
        paths.append(p)
    return paths
