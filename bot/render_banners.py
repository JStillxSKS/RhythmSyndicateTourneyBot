"""PNG announcement / hero banners — red · black · steel + RS logo."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import ASSETS_DIR, CAPTAIN_BURDEN_WEEK, LOGO_PATH, SEASON_WEEKS
from theme import HERO_ATTACHMENT_NAME

# Brand RGB
RED = (225, 6, 0)
RED_DEEP = (155, 11, 11)
STEEL = (197, 204, 212)
STEEL_DIM = (139, 148, 158)
WHITE = (244, 246, 248)
BLACK = (5, 6, 7)
CARD = (18, 20, 23)


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
    # Circular mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...],
    outline: tuple[int, ...] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _text_center(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, ...],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((xy[0] - tw // 2, xy[1] - th // 2), text, font=font, fill=fill)


def render_hero_banner(
    *,
    week: int,
    season: str = "Season 1",
    status: str = "open",
    song: str | None = None,
    deadline: str | None = None,
    burden: bool = False,
    headline: str | None = None,
    kicker: str = "RHYTHM SYNDICATE PRESENTS",
) -> bytes:
    """Stadium / hero announcement banner — **mockup 02 HTML** first, Pillow fallback."""
    try:
        from render_html import render_hero_mockup_png

        png = render_hero_mockup_png(
            week=week,
            season=season,
            status=status,
            song=song,
            deadline=deadline,
            burden=burden,
            headline=headline,
            kicker=kicker.title() if kicker.isupper() else kicker,
        )
        if png:
            return png
    except Exception as e:
        print(f"Mockup hero HTML path failed, Pillow fallback: {e}")

    w, h = 960, 420
    img = Image.new("RGB", (w, h), BLACK)
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft red glow top-center
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((w // 2 - 280, -120, w // 2 + 280, 260), fill=(*RED, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(48))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Outer frame
    margin = 14
    draw.rounded_rectangle(
        (margin, margin, w - margin, h - margin),
        radius=18,
        outline=(42, 47, 54),
        width=2,
    )
    # Steel inner line
    draw.rounded_rectangle(
        (margin + 8, margin + 8, w - margin - 8, h - margin - 8),
        radius=14,
        outline=(55, 60, 68),
        width=1,
    )
    # Red corner brackets
    bracket = 28
    lw = 3
    # TL
    draw.line((margin + 6, margin + 6 + bracket, margin + 6, margin + 6), fill=RED, width=lw)
    draw.line((margin + 6, margin + 6, margin + 6 + bracket, margin + 6), fill=RED, width=lw)
    # BR
    draw.line((w - margin - 6, h - margin - 6 - bracket, w - margin - 6, h - margin - 6), fill=RED, width=lw)
    draw.line((w - margin - 6, h - margin - 6, w - margin - 6 - bracket, h - margin - 6), fill=RED, width=lw)

    # Logo
    logo = _load_logo(110)
    if logo:
        lx, ly = w // 2 - 55, 42
        # Ring
        draw.ellipse((lx - 4, ly - 4, lx + 114, ly + 114), outline=STEEL_DIM, width=2)
        img.paste(logo, (lx, ly), logo)
        draw = ImageDraw.Draw(img)

    font_kicker = _font(15, bold=True)
    font_hero = _font(52, bold=True)
    font_sub = _font(18)
    font_chip = _font(14, bold=True)

    cy = 175 if logo else 100
    _text_center(draw, (w // 2, cy), kicker, font_kicker, STEEL)

    if headline:
        main = headline.upper()
        accent = ""
    elif burden:
        main = "CAPTAIN'S BURDEN"
        accent = f"WEEK {week}"
    elif status.lower() == "closed":
        main = f"WEEK {week}"
        accent = "CLOSED"
    else:
        main = f"WEEK {week}"
        accent = "OPEN"

    # Split main + accent for coloring
    font_big = font_hero
    if accent and not headline:
        left = main + " "
        # measure
        bb_l = draw.textbbox((0, 0), left, font=font_big)
        bb_a = draw.textbbox((0, 0), accent, font=font_big)
        total_w = (bb_l[2] - bb_l[0]) + (bb_a[2] - bb_a[0])
        x0 = w // 2 - total_w // 2
        y0 = cy + 28
        draw.text((x0, y0), left, font=font_big, fill=WHITE)
        draw.text((x0 + (bb_l[2] - bb_l[0]), y0), accent, font=font_big, fill=RED)
    else:
        _text_center(draw, (w // 2, cy + 48), main, font_big, WHITE)
        if accent:
            _text_center(draw, (w // 2, cy + 100), accent, font_big, RED)

    sub_bits = [season, f"Teams of 2", f"{SEASON_WEEKS}-week season"]
    if song:
        sub_bits = [song] + sub_bits[:1]
    sub = " · ".join(sub_bits)
    _text_center(draw, (w // 2, h - 95), sub[:72], font_sub, STEEL_DIM)

    # Chips row
    chips: list[tuple[str, bool]] = []
    st = status.lower()
    if st == "open":
        chips.append(("NOW LIVE", True))
    elif st == "closed":
        chips.append(("CLOSED", True))
    else:
        chips.append(("SCHEDULED", False))
    if deadline:
        chips.append((deadline[:28].upper(), False))
    if burden:
        chips.append(("CAPTAIN + TEAMMATE × 2", True))
    else:
        chips.append(("CLASSIC · FUSION · ARCADE", False))

    chip_fonts = font_chip
    # measure chips
    pads_x, pads_y, gap = 14, 8, 10
    chip_sizes = []
    for text, _hot in chips:
        bb = draw.textbbox((0, 0), text, font=chip_fonts)
        chip_sizes.append((bb[2] - bb[0] + pads_x * 2, bb[3] - bb[1] + pads_y * 2, text, _hot))
    total = sum(s[0] for s in chip_sizes) + gap * (len(chip_sizes) - 1)
    x = w // 2 - total // 2
    y = h - 58
    for cw, ch, text, hot in chip_sizes:
        fill = (80, 12, 12) if hot else (30, 34, 40)
        outline = RED if hot else (70, 76, 86)
        color = (255, 140, 130) if hot else STEEL
        _rounded_rect(draw, (x, y, x + cw, y + ch), 6, fill, outline, 1)
        bb = draw.textbbox((0, 0), text, font=chip_fonts)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((x + (cw - tw) // 2, y + (ch - th) // 2 - 1), text, font=chip_fonts, fill=color)
        x += cw + gap

    # Bottom pulse line
    draw.rectangle((margin + 20, h - margin - 4, w - margin - 20, h - margin - 1), fill=RED)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_hero_from_state(state: dict[str, Any], *, mode: str = "week") -> bytes:
    """Build hero from live tournament state."""
    from datetime import datetime

    from config import RS_TZ
    from state import get_week

    season = state.get("season") or {}
    week_n = int(season.get("current_week") or 1)
    week = get_week(state, week_n)
    status = (week.get("status") or "scheduled").lower()
    burden = week_n == CAPTAIN_BURDEN_WEEK or mode == "burden"

    song = week.get("song_title") or None
    if song and week.get("song_artist"):
        song = f"{song} — {week['song_artist']}"

    deadline = None
    close_at = week.get("close_at")
    if close_at:
        try:
            dt = datetime.fromisoformat(close_at.replace("Z", "+00:00")).astimezone(RS_TZ)
            deadline = f"Closes {dt.strftime('%a %I:%M %p %Z')}"
        except ValueError:
            deadline = "See deadline"

    headline = None
    kicker = "RHYTHM SYNDICATE PRESENTS"
    if mode == "announce":
        kicker = "OFFICIAL ANNOUNCEMENT"
    elif mode == "burden" or burden and mode == "week":
        headline = None  # uses burden path
        mode = "burden"

    return render_hero_banner(
        week=week_n,
        season=season.get("name") or "Season 1",
        status=status,
        song=song,
        deadline=deadline,
        burden=burden or mode == "burden",
        headline=headline,
        kicker=kicker,
    )


def hero_discord_file(png_bytes: bytes, filename: str = HERO_ATTACHMENT_NAME) -> Any:
    import discord

    return discord.File(io.BytesIO(png_bytes), filename=filename)


def write_preview(path: Path | None = None, **kwargs: Any) -> Path:
    """Dev helper: write a sample banner to assets/mockups."""
    out = path or (ASSETS_DIR / "mockups" / "live-hero-preview.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = render_hero_banner(**kwargs) if kwargs else render_hero_banner(week=1, status="open")
    out.write_bytes(data)
    return out
