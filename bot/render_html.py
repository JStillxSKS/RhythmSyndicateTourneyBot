"""
Production card renders using the **same CSS as the announcement mockups**.

Pipeline:
  1. Build a one-card HTML page (mockup styles + live text)
  2. Edge headless --screenshot
  3. Return PNG bytes

Falls back to None if Edge missing / screenshot fails — callers use Pillow path.
"""
from __future__ import annotations

import html as html_lib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from config import ASSETS_DIR, LOGO_PATH, PROJECT_DIR

# ---------------------------------------------------------------------------
# Mockup design tokens + shared styles (from announcement-mockups.html)
# ---------------------------------------------------------------------------

MOCKUP_CSS = """
:root {
  --rs-red: #e10600;
  --rs-red-deep: #9b0b0b;
  --rs-red-glow: rgba(225, 6, 0, 0.45);
  --rs-steel: #c5ccd4;
  --rs-steel-dim: #8b949e;
  --rs-black: #0a0a0a;
  --rs-card: #121417;
  --rs-card-2: #181b20;
  --rs-border: #2a2f36;
  --rs-white: #f4f6f8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: #050505;
  color: var(--rs-white);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  overflow: hidden;
}
.chip {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 999px;
  background: #1e232b;
  border: 1px solid var(--rs-border);
  color: var(--rs-steel);
  display: inline-block;
}
.chip.hot {
  border-color: rgba(225,6,0,0.55);
  color: #ff6b63;
  background: rgba(225,6,0,0.12);
}

/* --- m1 Discord embed classic --- */
.m1 {
  width: 720px;
  background: var(--rs-card);
  border-radius: 8px;
  border-left: 5px solid var(--rs-red);
  padding: 18px 20px 16px;
  display: grid;
  grid-template-columns: 1fr 88px;
  gap: 12px 16px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.55);
}
.m1 .eyebrow {
  grid-column: 1 / -1;
  color: var(--rs-steel-dim);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.m1 h2 {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--rs-white);
}
.m1 h2 span { color: var(--rs-red); }
.m1 .body {
  grid-column: 1;
  color: #c8ced6;
  font-size: 14.5px;
  line-height: 1.55;
  margin-top: 4px;
}
.m1 .meta {
  grid-column: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.m1 .logo {
  grid-column: 2;
  grid-row: 2 / 4;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 0 0 2px #2a2f36, 0 0 18px var(--rs-red-glow);
  align-self: start;
}
.m1 .foot {
  grid-column: 1 / -1;
  border-top: 1px solid #232830;
  margin-top: 14px;
  padding-top: 10px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--rs-steel-dim);
  letter-spacing: 0.04em;
}

/* --- m2 Hero banner --- */
.m2 {
  width: 720px;
  height: 320px;
  border-radius: 14px;
  overflow: hidden;
  position: relative;
  background:
    radial-gradient(ellipse 80% 70% at 50% 20%, rgba(225,6,0,0.28), transparent 55%),
    radial-gradient(ellipse 60% 50% at 80% 90%, rgba(140,150,165,0.12), transparent 50%),
    linear-gradient(180deg, #12151a 0%, #08090b 100%);
  border: 1px solid #2c3138;
  box-shadow: 0 16px 48px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(197,204,212,0.06);
}
.m2 .frame {
  position: absolute;
  inset: 10px;
  border: 1px solid rgba(197,204,212,0.18);
  border-radius: 10px;
  pointer-events: none;
}
.m2 .frame::before, .m2 .frame::after {
  content: "";
  position: absolute;
  width: 28px; height: 28px;
  border: 2px solid var(--rs-red);
}
.m2 .frame::before { top: -1px; left: -1px; border-right: 0; border-bottom: 0; }
.m2 .frame::after { bottom: -1px; right: -1px; border-left: 0; border-top: 0; }
.m2-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px 32px;
  position: relative;
  z-index: 1;
}
.m2 .logo {
  width: 92px;
  height: 92px;
  border-radius: 50%;
  object-fit: cover;
  margin-bottom: 14px;
  box-shadow: 0 0 0 3px rgba(197,204,212,0.25), 0 0 28px var(--rs-red-glow);
}
.m2 .kicker {
  font-size: 11px;
  letter-spacing: 0.35em;
  color: var(--rs-steel);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.m2 h2 {
  font-size: 42px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  line-height: 1;
  text-shadow: 0 0 40px var(--rs-red-glow);
}
.m2 h2 em {
  font-style: normal;
  color: var(--rs-red);
}
.m2 .sub {
  margin-top: 12px;
  font-size: 14px;
  color: var(--rs-steel-dim);
  letter-spacing: 0.08em;
}
.m2 .bar {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
}
.m2 .bar span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  padding: 7px 12px;
  border-radius: 4px;
  background: rgba(225,6,0,0.15);
  border: 1px solid rgba(225,6,0,0.45);
  color: #ff8a84;
}
.m2 .bar span.steel {
  background: rgba(197,204,212,0.08);
  border-color: rgba(197,204,212,0.28);
  color: var(--rs-steel);
}
.m2 .pulse {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--rs-red), transparent);
  opacity: 0.9;
}

/* --- m4 Ops strip --- */
.m4 {
  width: 720px;
  background: var(--rs-card-2);
  border-radius: 12px;
  border: 1px solid var(--rs-border);
  overflow: hidden;
  box-shadow: 0 14px 40px rgba(0,0,0,0.55);
}
.m4-top {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: linear-gradient(90deg, rgba(225,6,0,0.18), transparent 55%), #14181e;
  border-bottom: 1px solid #2a3038;
}
.m4-top .logo {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 0 0 2px rgba(197,204,212,0.25);
}
.m4-top .titles { flex: 1; }
.m4-top .titles .small {
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--rs-steel-dim);
}
.m4-top .titles h2 {
  font-size: 20px;
  font-weight: 700;
  margin-top: 2px;
}
.m4-top .status {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(225,6,0,0.18);
  border: 1px solid rgba(225,6,0,0.5);
  color: #ff7a73;
  white-space: nowrap;
}
.m4-top .status.closed {
  background: rgba(197,204,212,0.1);
  border-color: rgba(197,204,212,0.35);
  color: var(--rs-steel);
}
.m4-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: #2a3038;
}
.m4-grid .cell {
  background: #151920;
  padding: 16px 18px;
}
.m4-grid .cell .k {
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--rs-steel-dim);
  margin-bottom: 6px;
}
.m4-grid .cell .v {
  font-size: 15px;
  font-weight: 600;
  color: var(--rs-white);
}
.m4-grid .cell .v.red { color: #ff6b63; }
.m4-bottom {
  padding: 14px 18px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  background: #10141a;
}
.m4-bottom .note {
  margin-left: auto;
  font-size: 11px;
  color: var(--rs-steel-dim);
}

/* --- m3 Poster --- */
.m3 {
  width: 420px;
  height: 620px;
  border-radius: 12px;
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(10,10,10,0.2) 0%, rgba(10,10,10,0.85) 55%, #050505 100%),
    radial-gradient(circle at 50% 28%, rgba(225,6,0,0.35), transparent 50%),
    #0b0c0e;
  border: 1px solid #333940;
  box-shadow: 0 20px 50px rgba(0,0,0,0.65);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 36px 28px 28px;
  text-align: center;
}
.m3 .steel-ring {
  position: absolute;
  top: 48px;
  width: 210px;
  height: 210px;
  border-radius: 50%;
  border: 1px solid rgba(197,204,212,0.22);
  box-shadow: 0 0 40px rgba(225,6,0,0.2), inset 0 0 30px rgba(0,0,0,0.5);
}
.m3 .logo {
  width: 168px;
  height: 168px;
  border-radius: 50%;
  object-fit: cover;
  position: relative;
  z-index: 1;
  margin-top: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
}
.m3 .tag {
  margin-top: 28px;
  font-size: 11px;
  letter-spacing: 0.4em;
  color: var(--rs-steel);
  text-transform: uppercase;
}
.m3 h2 {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.m3 h2 .red { color: var(--rs-red); display: block; font-size: 40px; }
.m3 .rule {
  width: 72%;
  height: 2px;
  margin: 18px auto;
  background: linear-gradient(90deg, transparent, var(--rs-red), var(--rs-steel), var(--rs-red), transparent);
  opacity: 0.85;
}
.m3 .copy {
  font-size: 14px;
  color: #b7bec7;
  line-height: 1.55;
  max-width: 300px;
}
.m3 .footer-block {
  margin-top: auto;
  width: 100%;
  padding-top: 18px;
  border-top: 1px solid rgba(197,204,212,0.15);
}
.m3 .footer-block strong {
  display: block;
  font-size: 13px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--rs-white);
  margin-bottom: 6px;
}
.m3 .footer-block span {
  font-size: 12px;
  color: var(--rs-steel-dim);
  letter-spacing: 0.06em;
}
.m3 .rs4l {
  margin-top: 14px;
  font-size: 12px;
  letter-spacing: 0.35em;
  color: var(--rs-red);
  font-weight: 700;
}

/* --- m5 Cinematic --- */
.m5 {
  width: 720px;
  height: 280px;
  border-radius: 14px;
  position: relative;
  overflow: hidden;
  background: #050607;
  border: 1px solid #2a2f36;
  box-shadow: 0 16px 48px rgba(0,0,0,0.65);
}
.m5 .bg-logo {
  position: absolute;
  right: -40px;
  top: 50%;
  transform: translateY(-50%);
  width: 340px;
  height: 340px;
  border-radius: 50%;
  object-fit: cover;
  opacity: 0.18;
  filter: grayscale(0.15) contrast(1.1);
  mask-image: radial-gradient(circle, black 40%, transparent 72%);
  -webkit-mask-image: radial-gradient(circle, black 40%, transparent 72%);
}
.m5 .vignette {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, #050607 18%, rgba(5,6,7,0.82) 48%, rgba(5,6,7,0.35) 100%),
    radial-gradient(ellipse at 20% 50%, rgba(225,6,0,0.18), transparent 55%);
  pointer-events: none;
}
.m5 .content {
  position: relative;
  z-index: 2;
  height: 100%;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 420px;
}
.m5 .badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--rs-steel);
  margin-bottom: 14px;
}
.m5 .badge i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--rs-red);
  box-shadow: 0 0 10px var(--rs-red);
  display: inline-block;
}
.m5 h2 {
  font-size: 32px;
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.01em;
}
.m5 h2 span { color: var(--rs-red); }
.m5 p {
  margin-top: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: #aeb6c0;
}
.m5 .cta-row {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.m5 .cta {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 10px 14px;
  background: linear-gradient(180deg, #e10600, #9b0b0b);
  border-radius: 6px;
  color: white;
  box-shadow: 0 6px 18px rgba(225,6,0,0.35);
}
.m5 .cta-sub {
  font-size: 12px;
  color: var(--rs-steel-dim);
  letter-spacing: 0.04em;
}
.m5 .ecg {
  position: absolute;
  left: 32px;
  right: 32px;
  bottom: 18px;
  height: 18px;
  opacity: 0.55;
  background: linear-gradient(90deg,
    transparent 0%, var(--rs-red) 8%, transparent 10%,
    transparent 18%, var(--rs-red) 22%, transparent 24%,
    transparent 40%, #c5ccd4 48%, transparent 52%,
    transparent 70%, var(--rs-red) 78%, transparent 82%);
}
"""


def _esc(s: str | None) -> str:
    return html_lib.escape(s or "")


def _logo_uri() -> str:
    if LOGO_PATH.is_file():
        return LOGO_PATH.resolve().as_uri()
    return ""


def _find_edge() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for p in candidates:
        if p and p.is_file():
            return p
    return None


def html_available() -> bool:
    return _find_edge() is not None and LOGO_PATH.is_file()


def _page(body: str, *, width: int, height: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/>
<style>
{MOCKUP_CSS}
body {{ width: {width}px; height: {height}px; padding: 0; margin: 0; }}
.stage {{ width: {width}px; height: {height}px; display: flex; align-items: flex-start; justify-content: flex-start; }}
</style>
</head>
<body><div class="stage">{body}</div></body></html>
"""


def screenshot_html(html: str, *, width: int, height: int, timeout: int = 25) -> bytes | None:
    """Write HTML temp file, Edge headless screenshot, return PNG bytes."""
    edge = _find_edge()
    if not edge:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="rs-html-") as td:
            tdir = Path(td)
            html_path = tdir / "card.html"
            png_path = tdir / "card.png"
            html_path.write_text(html, encoding="utf-8")
            # Extra margin so shadow isn't clipped
            win_w = width + 40
            win_h = height + 40
            cmd = [
                str(edge),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={win_w},{win_h}",
                f"--screenshot={png_path}",
                html_path.as_uri(),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
            if not png_path.is_file():
                return None
            data = png_path.read_bytes()
            if len(data) < 500 or data[:8] != b"\x89PNG\r\n\x1a\n":
                return None
            # Crop to content if Edge adds padding
            try:
                from PIL import Image
                import io

                im = Image.open(io.BytesIO(data)).convert("RGB")
                # Trim near-black margin
                return _trim_and_fit(im, width, height)
            except Exception:
                return data
    except Exception as e:
        print(f"HTML screenshot failed: {e}")
        return None


def _trim_and_fit(im: Any, target_w: int, target_h: int) -> bytes:
    import io

    from PIL import Image

    # Find non-near-black bbox
    px = im.load()
    w, h = im.size
    min_x, min_y, max_x, max_y = w, h, 0, 0
    found = False
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r + g + b > 24:
                found = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if not found:
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    pad = 4
    crop = im.crop(
        (
            max(0, min_x - pad),
            max(0, min_y - pad),
            min(w, max_x + pad + 1),
            min(h, max_y + pad + 1),
        )
    )
    # Don't upscale wildly; keep card sharp
    buf = io.BytesIO()
    crop.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Card builders (mockup markup + live text)
# ---------------------------------------------------------------------------


def build_hero_html(
    *,
    week: int,
    season: str = "Season 1",
    status: str = "open",
    song: str | None = None,
    deadline: str | None = None,
    burden: bool = False,
    headline: str | None = None,
    kicker: str = "Rhythm Syndicate presents",
) -> str:
    logo = _logo_uri()
    st = (status or "open").lower()
    if headline:
        main = _esc(headline)
        accent = ""
        h2 = f"<h2>{main}</h2>"
    elif burden:
        h2 = f"<h2>Captain's <em>Burden</em></h2>"
    elif st == "closed":
        h2 = f"<h2>Week {int(week)} <em>Closed</em></h2>"
    else:
        h2 = f"<h2>Week {int(week)} <em>Open</em></h2>"

    sub_bits = [season, "Teams of 2", "Four-week grind"]
    if song:
        sub_bits = [song, season]
    sub = _esc(" · ".join(sub_bits)[:80])

    chips = []
    if st == "open":
        chips.append('<span>Now Live</span>')
    elif st == "closed":
        chips.append('<span>Closed</span>')
    else:
        chips.append('<span class="steel">Scheduled</span>')
    if deadline:
        chips.append(f'<span class="steel">{_esc(deadline[:40])}</span>')
    if burden:
        chips.append('<span class="steel">Captain + Teammate × 2</span>')
    else:
        chips.append('<span class="steel">3 Divisions</span>')

    body = f"""
    <div class="m2">
      <div class="frame"></div>
      <div class="m2-inner">
        <img class="logo" src="{logo}" alt="RS" />
        <div class="kicker">{_esc(kicker)}</div>
        {h2}
        <div class="sub">{sub}</div>
        <div class="bar">{"".join(chips)}</div>
      </div>
      <div class="pulse"></div>
    </div>
    """
    return _page(body, width=720, height=320)


def build_ops_html(
    *,
    week: int,
    season: str = "Season 1",
    status: str = "open",
    song: str | None = None,
    opens: str | None = None,
    closes: str | None = None,
    burden: bool = False,
) -> str:
    logo = _logo_uri()
    st = (status or "scheduled").lower()
    if st == "open":
        status_cls, status_txt = "", "● Open"
    elif st == "closed":
        status_cls, status_txt = "closed", "● Closed"
    else:
        status_cls, status_txt = "closed", "○ Scheduled"

    title = f"Week {int(week)} scoring window"
    if burden:
        title = f"Week {int(week)} · Captain's Burden"

    body = f"""
    <div class="m4">
      <div class="m4-top">
        <img class="logo" src="{logo}" alt="RS" />
        <div class="titles">
          <div class="small">Rhythm Syndicate · {_esc(season)}</div>
          <h2>{_esc(title)}</h2>
        </div>
        <div class="status {status_cls}">{status_txt}</div>
      </div>
      <div class="m4-grid">
        <div class="cell">
          <div class="k">Opens</div>
          <div class="v">{_esc(opens or "—")}</div>
        </div>
        <div class="cell">
          <div class="k">Closes</div>
          <div class="v red">{_esc(closes or "—")}</div>
        </div>
        <div class="cell">
          <div class="k">Song</div>
          <div class="v">{_esc((song or "TBD")[:40])}</div>
        </div>
      </div>
      <div class="m4-bottom">
        <span class="chip">Classic</span>
        <span class="chip">Fusion</span>
        <span class="chip">Arcade</span>
        {"<span class='chip hot'>Captain's Burden</span>" if burden else ""}
        <span class="note">Staff: /rs · Players: /tourney</span>
      </div>
    </div>
    """
    return _page(body, width=720, height=210)


def build_embed_html(
    *,
    title: str,
    title_accent: str | None = None,
    body: str,
    chips: list[tuple[str, bool]] | None = None,
    foot_left: str = "RS TOURNEY BOT · ANNOUNCEMENT",
    foot_right: str = "RS4L",
) -> str:
    logo = _logo_uri()
    if title_accent:
        h2 = f"{_esc(title)} <span>{_esc(title_accent)}</span>"
    else:
        h2 = _esc(title)
    chip_html = ""
    for text, hot in chips or []:
        cls = "chip hot" if hot else "chip"
        chip_html += f'<span class="{cls}">{_esc(text)}</span>'
    card = f"""
    <div class="m1">
      <div class="eyebrow">Rhythm Syndicate · Official</div>
      <div>
        <h2>{h2}</h2>
        <p class="body">{_esc(body)}</p>
        <div class="meta">{chip_html}</div>
      </div>
      <img class="logo" src="{logo}" alt="RS" />
      <div class="foot">
        <span>{_esc(foot_left)}</span>
        <span>{_esc(foot_right)}</span>
      </div>
    </div>
    """
    return _page(card, width=720, height=220)


def build_cinematic_html(
    *,
    headline: str,
    accent: str | None = None,
    body: str,
    cta: str = "Standings live",
    cta_sub: str = "RS · Season 1",
    badge: str = "Official Announcement",
) -> str:
    logo = _logo_uri()
    if accent:
        h2 = f"{_esc(headline)}<br /><span>{_esc(accent)}</span>"
    else:
        h2 = _esc(headline)
    card = f"""
    <div class="m5">
      <img class="bg-logo" src="{logo}" alt="" />
      <div class="vignette"></div>
      <div class="content">
        <div class="badge"><i></i> {_esc(badge)}</div>
        <h2>{h2}</h2>
        <p>{_esc(body)}</p>
        <div class="cta-row">
          <div class="cta">{_esc(cta)}</div>
          <div class="cta-sub">{_esc(cta_sub)}</div>
        </div>
      </div>
      <div class="ecg"></div>
    </div>
    """
    return _page(card, width=720, height=280)


def build_poster_html(
    *,
    tag: str = "Season One",
    line1: str = "The beat",
    line2: str = "Drops",
    copy: str = "",
    footer_strong: str = "Saturday · 10:00 AM PST",
    footer_span: str = "Classic · Fusion · Arcade",
) -> str:
    logo = _logo_uri()
    card = f"""
    <div class="m3">
      <div class="steel-ring"></div>
      <img class="logo" src="{logo}" alt="RS" />
      <div class="tag">{_esc(tag)}</div>
      <h2>
        {_esc(line1)}
        <span class="red">{_esc(line2)}</span>
      </h2>
      <div class="rule"></div>
      <p class="copy">{_esc(copy)}</p>
      <div class="footer-block">
        <strong>{_esc(footer_strong)}</strong>
        <span>{_esc(footer_span)}</span>
        <div class="rs4l">RS4L</div>
      </div>
    </div>
    """
    return _page(card, width=420, height=620)


# ---------------------------------------------------------------------------
# High-level: PNG or None
# ---------------------------------------------------------------------------


def render_hero_mockup_png(**kwargs: Any) -> bytes | None:
    if not html_available():
        return None
    return screenshot_html(build_hero_html(**kwargs), width=720, height=320)


def render_ops_mockup_png(**kwargs: Any) -> bytes | None:
    if not html_available():
        return None
    return screenshot_html(build_ops_html(**kwargs), width=720, height=220)


def render_embed_mockup_png(**kwargs: Any) -> bytes | None:
    if not html_available():
        return None
    return screenshot_html(build_embed_html(**kwargs), width=720, height=240)


def render_cinematic_mockup_png(**kwargs: Any) -> bytes | None:
    if not html_available():
        return None
    return screenshot_html(build_cinematic_html(**kwargs), width=720, height=280)


def render_poster_mockup_png(**kwargs: Any) -> bytes | None:
    if not html_available():
        return None
    return screenshot_html(build_poster_html(**kwargs), width=420, height=620)


def write_live_mockup_previews() -> list[Path]:
    """Write production mockup-path previews next to assets/mockups/live-mockup/."""
    out_dir = ASSETS_DIR / "mockups" / "live-mockup"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    jobs = [
        ("hero-open.png", lambda: render_hero_mockup_png(week=1, status="open", song="Paranoid — Black Sabbath", deadline="Closes Fri 11:59 PM PST")),
        ("hero-closed.png", lambda: render_hero_mockup_png(week=2, status="closed", song="Riot")),
        ("hero-burden.png", lambda: render_hero_mockup_png(week=4, status="open", burden=True, song="Finale")),
        ("ops-open.png", lambda: render_ops_mockup_png(week=2, status="open", song="Paranoid — Black Sabbath", opens="Sat 10:00 AM PST", closes="Fri 11:59 PM PST")),
        ("embed-live.png", lambda: render_embed_mockup_png(
            title="Season 1 is",
            title_accent="LIVE",
            body="Week 1 scoring is open. Pair up, pick your division, and put points on the board.",
            chips=[("Week 1 Open", True), ("Sat 10:00 AM PST", False), ("Classic · Fusion · Arcade", False)],
        )),
        ("cinematic-burden.png", lambda: render_cinematic_mockup_png(
            headline="Captain's Burden",
            accent="Week 4",
            body="Final stretch. Captain score + Teammate × 2. Leave nothing on the kit.",
        )),
    ]
    for name, fn in jobs:
        data = fn()
        if data:
            p = out_dir / name
            p.write_bytes(data)
            paths.append(p)
            print(f"wrote {p} ({len(data)} bytes)")
        else:
            print(f"skip {name} (html render unavailable)")
    return paths
