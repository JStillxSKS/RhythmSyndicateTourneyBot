# RS Tournament Bot — pickup checklist

**Last updated:** 2026-07-15 (Windows · Grok Lesnar)  
**Project:** `C:\Users\JStillxSKS\Desktop\RhythmSyndicateTourneyBot\`  
**Host:** **Windows only** (do not hand to Kali)  
**Build string:** `BOT_VERSION` in `bot/config.py` → currently **`2026-07-16-golive-v1`**  
**Prove live:** `/tourney help` and `/rs where` must show that string after deploy  

Master bridge: `Desktop\GROK_BRIDGE.md` (also notes this project).

---

## Legend

- [x] Done  
- [ ] Not done / blocked on people or accounts  
- [~] Partial / in progress  

---

## A. Design & agreements

- [x] Season 1 format locked (teams of 2, 3 divisions, 4 weeks, Captain’s Burden week 4)
- [x] Registration: Sesh; staff import teams (bot does not own signup)
- [x] Command split: players `/tourney` · staff `/rs` (not `/rs-admin`)
- [x] Brand: logo filed; red / black / steel (`assets/rhythm-syndicate-logo.jpg`)
- [x] Bo goal: reliable Season 1 first; expand later
- [x] Parallel lanes: foundation (this) + visuals (theme/heroes/mockups already in tree)
- [x] Night-before-go-live: switch env to public tourney channel + redeploy (buffer, not morning-of)
- [x] Prefer private lab channel over permanent clutter; cut lab/test server after live is solid (confirm with Laura)
- [ ] Laura / Bo final yay-nay on any open product nits (calendar flow, announce tone, etc.)

---

## B. Code foundation (local Windows)

- [x] Project scaffold (`bot/`, `requirements.txt`, `.env.example`, `.gitignore`, `data/`)
- [x] Config + `BOT_VERSION` prove-live pattern
- [x] JSON state: season, weeks, teams, submissions + `.bak.json` on save
- [x] Rules engine: best verified, missing=0, Captain’s Burden, cumulative standings
- [x] Score embed parse + intake (✅ / ⏳); mode≠division warning
- [x] Manual `/rs score set`; `/rs submission approve`
- [x] Week open/close + Friday 11:59 PT default deadline helper
- [x] Player commands: status, my-team, my-score, standings, rules, help
- [x] Staff commands: week, song, standings, team add/replace/list, submission, dashboard, calendar, announce, where
- [x] Dashboard embeds + logo; visuals theme/hero integration present
- [x] Health server for Render (`PORT` + `/health`)
- [x] Offline tests: `bot/test_rules.py`, `bot/test_deadline.py`, `bot/smoke_state.py`
- [x] Go-live battery (2026-07-16): `playground.py` (20k flood), `test_golive.py`, `test_extra_stress.py` — all PASS; report `GO_LIVE_TEST_REPORT.md`
- [x] Hardening: message_id dedupe, score set `week=` without moving current week, embed 1024 pack, state write lock
- [x] Docs: README, SETUP, OPERATOR_GUIDE, RENDER, DISCORD_SETUP.pdf
- [~] Visuals polish lane (mockups / heroes / theme) — other tab; consume, don’t fight
- [ ] GitHub repo (optional; not required for local)
- [ ] Full end-to-end Discord smoke on a live process (needs token + running bot)

---

## C. Discord application (user / Laura side)

- [ ] Discord application created (name e.g. RS Tourney)
- [ ] Bot user + token copied into **local** `.env` only (never bridge/chat)
- [ ] **Message Content Intent** ON
- [ ] Invite with scopes: `bot` + `applications.commands`
- [ ] Permissions (planned / user handling):
  - [ ] View Channel, Send Messages, Embed Links, Attach Files
  - [ ] Read Message History, Add Reactions
  - [ ] Manage Messages (pin)
  - [ ] Create Public Threads (+ Send in Threads) — optional, user OK with it
- [ ] Bot invited to **Rhythm Syndicate** server
- [ ] Bot role can see intended channels
- [ ] IDs collected: `RS_GUILD_ID`, `RS_CHANNEL_ID`, `RS_ADMIN_ROLE_IDS` (± submit channel)
- [ ] Local `.env` filled from `.env.example`
- [ ] Optional: private **lab channel** (only user + Laura + bot) for playground
- [ ] Slash commands visible (`/tourney`, `/rs`) when bot is running

**PDF checklist for her/you:**  
`Desktop\Rhythm_Syndicate_Tourney_Bot_Discord_Setup.pdf`  
and `RhythmSyndicateTourneyBot\DISCORD_SETUP.pdf`

---

## D. Local prove (before her Render)

- [ ] `pip install -r requirements.txt`
- [ ] `python bot/main.py` stays online
- [ ] Logs: `RS TOURNEY BOT ONLINE BOT_VERSION=…`
- [ ] `/tourney help` → correct build
- [ ] `/rs where` → guild/channel/env look right
- [ ] Lab: `/rs team add` (you + her or alts) → `/rs song set` → `/rs week open`
- [ ] Forward Smash Drums score embed → ✅ or ⏳
- [ ] `/rs dashboard post` + pin
- [ ] Optional: `/rs calendar post` with a test image
- [ ] `/rs week close` → late path / approve
- [ ] Restart bot → state still there (`data/rs_state.json`)

---

## E. Laura’s Render (production host — her account)

- [ ] Repo or upload of this project on her Render (or GitHub she connects)
- [ ] Web service: `pip install -r requirements.txt` · start `python bot/main.py` · health `/health`
- [ ] Env secrets on Render (not in git):
  - [ ] `DISCORD_TOKEN`
  - [ ] `RS_GUILD_ID`
  - [ ] `RS_CHANNEL_ID` (lab first, then live channel night-before)
  - [ ] `RS_ADMIN_ROLE_IDS`
  - [ ] Optional: `RS_SUBMIT_CHANNEL_ID`
- [ ] Deploy green + logs show online + version
- [ ] Her machine not required for uptime after this

**Note:** You do not control her Render; handoff = this folder + SETUP/RENDER + env list.

---

## F. Night before Season 1 open (switch to live)

- [ ] Freeze non-critical code changes if possible
- [ ] Set `RS_CHANNEL_ID` (and submit if any) → **public tourney channel**
- [ ] Redeploy / restart so env sticks
- [ ] Prove: `/rs where`, `/tourney help`, dashboard post in **public** channel
- [ ] Confirm not still aimed at lab
- [ ] Optional: delete/archive lab channel + any extra test server (cleaner; confirm with Laura)
- [ ] State backup: download `data/rs_state.json` if teams already imported on Render disk (ephemeral risk — see RENDER.md)

---

## G. Season 1 ops (after open)

- [ ] Import all teams: `/rs team add` (or batch later if built)
- [ ] Each week: `/rs song set` → `/rs week open` → dashboard / announce
- [ ] Mid-week: standings update as needed
- [ ] Deadline: `/rs week close` · approve lates
- [ ] Week 4: Captain’s Burden auto in rules
- [ ] End season: standings final · future features only after stable

---

## H. Explicitly later / not foundation blockers

- [ ] Self-serve team invites
- [ ] Round robin automation
- [ ] Hall of Fame / website / CSV export
- [ ] Full OCR screenshots (embeds first)
- [ ] Permanent fancy image calendars automation beyond `/rs calendar post`
- [ ] Persistent DB if free Render disk wipes state (backup discipline or paid disk)

---

## Next session — start here (priority order)

1. **Check Discord progress with user** — app invited? `.env` ready? lab channel?
2. If yes → **local `python bot/main.py`** and run section **D** smoke  
3. If no Discord yet → only safe code polish or wait; do not invent her token  
4. Prep **Render handoff blurb** for Laura when she’s ready (section E)  
5. Do **not** point production at public channel until night-before plan  
6. Read this file + `OPERATOR_GUIDE.md` + bridge RS section before coding  

### Quick commands (Windows)

```text
cd Desktop\RhythmSyndicateTourneyBot
pip install -r requirements.txt
cd bot
python test_rules.py
python test_deadline.py
python smoke_state.py
cd ..
python bot\main.py
```

### Key paths

| Path | Role |
|------|------|
| `bot/main.py` | Entry |
| `bot/config.py` | Env + `BOT_VERSION` |
| `bot/commands_admin.py` | `/rs` |
| `bot/commands_player.py` | `/tourney` |
| `bot/rules.py` / `scores.py` / `state.py` | Domain |
| `bot/dashboard.py` / `theme.py` / `render_banners.py` | Presentation |
| `data/rs_state.json` | Live state (gitignored) |
| `.env` | Secrets (gitignored) |

---

## Session log (checklist-level)

### 2026-07-15
- Foundation + visuals merged in tree; `foundation-v3`: calendar post, pin, where, team list, score set, deadline helper, state bak, mode warning
- User: Discord invite in progress; waiting on Laura; Render = her side
- User: lab channel idea; night-before live switch; cut extra server/channel after solid
- Blocked on: her Discord/Render + yay for live channel strategy
- Next: Discord smoke when `.env` exists; else park
