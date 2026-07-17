# Visuals — mockups as production

## Principle
The announcement mockups (`assets/mockups/01`…`05`) are the **source of truth**.  
Live bot art uses the **same CSS** via `bot/render_html.py` (Edge headless screenshot).

## Pipeline
1. Build HTML card with mockup styles + live text  
2. Edge `--headless --screenshot`  
3. PNG bytes → Discord attachment  
4. If Edge/logo missing → Pillow fallback (`render_banners.py` / `render_boards.py`)

## What uses mockup HTML
| Card | Mockup | Bot path |
|------|--------|----------|
| Hero / week open-close | 02 | `render_hero_banner` → announce, week open/close |
| Ops dashboard strip | 04 | `render_ops_strip` → dashboard, `/tourney status` |
| Embed classic | 01 | default `/rs announce` image |
| Cinematic | 05 | Captain’s Burden announce |
| Poster | 03 | available via `render_poster_mockup_png` (pin moments later) |

## Previews
```text
cd bot
python -c "from render_html import write_live_mockup_previews; write_live_mockup_previews()"
```
Output: `assets/mockups/live-mockup/`

## Requirements
- Windows + **Microsoft Edge** on the host that generates images  
- Logo at `assets/rhythm-syndicate-logo.jpg`  
- Render free tier: Edge may not be installed — Pillow fallback still works (lower fidelity)

## Editor (text only)

**Folder:** `visual-editor/`  
**Open:** double-click `visual-editor/index.html`  
or Desktop shortcut: `open-rs-visual-editor.bat`

- Same mockup designs (Hero / Ops / Embed / Poster / Cinematic)  
- Edit text fields → live preview → **Download PNG**  
- No bot connection; manual upload to Discord for now  

See `visual-editor/README.md`.
