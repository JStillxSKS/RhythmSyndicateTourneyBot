# Operator guide — Season 1

**Players:** `/tourney`  
**Staff:** `/rs` (Manage Server **or** role in `RS_ADMIN_ROLE_IDS`)

## Weekly loop

| When | Action |
|------|--------|
| After Sesh registration | `/rs team add` for each team |
| Song ready | `/rs song set` |
| Sat open | `/rs week open` (public hero + ops announce on by default) · `/rs dashboard post` |
| During week | Players forward score embeds; bot ✅ verified or ⏳ pending (branded cards) |
| Standings | `/rs standings update` |
| Fri close | `/rs week close` (public close banner on by default) |
| Lates | `/rs submission approve` (omit id to list pending) |
| Week 4 | Captain’s Burden auto: Captain + (Teammate × 2) |

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
- `/rs team add` · `/rs team replace` · `/rs team list`  
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
