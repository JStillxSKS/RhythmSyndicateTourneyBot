# Operator guide — Season 1

**Players:** `/tourney`  
**Staff:** `/rs` (Manage Server **or** role in `RS_ADMIN_ROLE_IDS`)

## Automation (default ON)

| Env | Default | Meaning |
|-----|---------|---------|
| `RS_AUTO_WEEK` | on | Sat 10:00 PT open · Fri 23:59 PT close |
| `RS_AUTO_ANNOUNCE` | on | Public open/close graphics with the clock |
| `RS_AUTO_DIGEST` | on | Wed ~noon PT missing-score post (if week open) |

Kill switch: set any of those to `0` / `false` / `off`.

### Fast test clock (test server only)

| Env | Meaning |
|-----|---------|
| `RS_TEST_TIME=1` | Season clock uses **virtual PT time** |
| `RS_TEST_VHOURS_PER_RMIN=1` | **1 real minute = 1 virtual hour** (default) |

Then:
1. Restart bot  
2. `/rs season test-reset` → **before open** (virtual Sat 9:50) → auto **open ~10 real minutes** later  
3. `/rs season test-reset` → **before close** (virtual Fri 23:50) → auto **close ~9 real minutes** later  
4. `/rs season status` shows virtual “now”

Do **not** leave `RS_TEST_TIME=1` on production.

**Once (pre-season):** `/rs team import` or `/rs team add` · `/rs song set` for weeks 1–4 · `/rs dashboard post` · `/rs standings update` once  
**Weekly (happy path):** nothing — play and forward scores  
**Exceptions:** late approve · roster · song override · `/rs week open|close` if needed  

`/rs season status` — song queue + auto flags · `/rs where` — build + auto flags  

## Weekly loop (manual fallback)

| When | Action |
|------|--------|
| After Sesh registration | `/rs team import` (CSV) or `/rs team add` |
| Songs | `/rs song set` for each week (can preload all 4) |
| Sat open | Auto, or `/rs week open` |
| During week | Players forward score embeds; boards auto-refresh (throttled) |
| Standings | Auto on verified scores, or `/rs standings update` |
| Fri close | Auto, or `/rs week close` |
| Lates | `/rs submission approve` |
| Week 4 | Captain’s Burden auto in math |

## Player commands

- `/tourney status` — week / song / deadline  
- `/tourney my-team`  
- `/tourney my-score`  
- `/tourney standings [division]`  
- `/tourney rules`  
- `/tourney help`  

## Staff commands

- `/rs week open` · `/rs week close` — optional `announce:false` to suppress public post  
- `/rs song set`  
- `/rs standings update`  
- `/rs team add` · `/rs team replace` · `/rs team list` · `/rs team import`  
- `/rs season status` — auto clock + song queue  
- `/rs score set` — manual verified score (testing / disputes)  
- `/rs submission approve`  
- `/rs dashboard post [pin]` — living board (pins by default; needs Manage Messages)  
- `/rs calendar post` — attach calendar image + pin (Laura calendars)  
- `/rs announce` — styles: default (hero+ops), week open/close, captain burden, embed only  
- `/rs verse post` — team vs team card  
  - **daily** (default) = HUD score duel for routine updates  
  - **fight / ring / poster / result / title** = big-moment art  
- `/rs where` — staff diagnostic (build string, env, counts)  

## Score rules (bot-enforced)

- Highest **verified** score only  
- Missing teammate = **0**  
- Closed week → pending until approve  
- Cumulative season standings per division  

## Brand / visuals

- Logo: `assets/rhythm-syndicate-logo.jpg` (red / black / steel)  
- Kit: `bot/theme.py` · heroes: `render_banners.py` · verse: `render_versus.py`  
- Public week open/close + announce = **hero banner** + **ops embed**  
- **Verse cards:** daily = HUD (03); big moments = fight / ring / poster / result / title  
- Build string: `/tourney help` or `/rs where` (`BOT_VERSION`)
