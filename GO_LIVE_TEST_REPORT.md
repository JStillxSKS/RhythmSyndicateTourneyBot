# Rhythm Syndicate Tourney Bot — Go-Live Test Report

**Date:** 2026-07-16 (Windows)  
**Agent:** Grok Lesnar  
**Build tested:** `BOT_VERSION=2026-07-16-golive-v1`  
**Project:** `Desktop/RhythmSyndicateTourneyBot/`  
**Scope:** Offline domain + stress + embed limits. **Not** a live Discord channel smoke (no token in this session).

---

## Executive summary

| Area | Verdict |
|------|---------|
| Scoring rules (best-of, missing=0, Captain’s Burden) | **PASS** |
| Score intake pipeline (verify / pending / approve) | **PASS** |
| Flood / re-forward / concurrent disk writes | **PASS** |
| Discord embed field size safety (large roster) | **PASS** (after harden) |
| Full weekend ops simulation | **PASS** |
| Live Discord process in channel | **NOT RUN** — needs `DISCORD_TOKEN` + lab channel |

**Bottom line:** Core tournament logic is solid for Season 1. Several go-live bugs were found in review and **fixed before** this report. The remaining risk is almost entirely **ops / Discord env**, not math.

---

## What we tested (not skimpy)

### Suites run

| Suite | Command | Result |
|-------|---------|--------|
| Rules unit | `python test_rules.py` | PASS |
| Deadline helper | `python test_deadline.py` | PASS |
| Offline smoke | `python smoke_state.py` | PASS |
| Go-live readiness | `python test_golive.py` | **56/56** PASS |
| Playground / flood | `python playground.py --teams 25 --flood 20000` | ALL PASS |
| Extra stress | `python test_extra_stress.py` | **51/51** PASS |
| Visuals / heroes | `python test_visuals.py` | PASS |
| Versus cards | `python test_verse.py` | PASS |

### Load numbers (peak)

| Scenario | Scale | Result |
|----------|-------|--------|
| Score flood | **20,000** attempts, **75** teams (25/div) | ~19k accepted, ~953 unregistered noise; **~20s**; standings **~249ms** |
| Throughput | **15,000** subs in memory | **~1,093/s**; 3-div standings **~149ms** |
| Concurrent disk | 8 threads × 25 saves | Final JSON valid, 200 rows |
| Concurrent race (extra) | 6 threads × 30 persists | 180 rows, file valid |
| Best-of spam | 500 scores one player | Correct max kept |
| Roster stress | **90 teams** (180 players) | Missing list + standings fields all **≤1024** chars |
| Full season chaos | 4 weeks, random no-shows | Ranks sorted, burden math OK |
| State corruption | bad JSON / wrong types | Falls back to empty shape safely |

### Behaviors covered

- Best verified score only counts; lower retries ignored  
- Missing teammate = 0  
- Captain’s Burden week 4 = Captain + (Teammate × 2)  
- Week open → auto-verify; week closed → pending → `/rs submission approve`  
- Same Discord `message_id` not double-counted (re-forward / double-fire)  
- Unregistered / inactive / zero / negative scores rejected  
- Division isolation (classic scores never appear on fusion board)  
- Tie-break: equal totals → alphabetical team name  
- Staff manual score for **past week** without moving `current_week`  
- Embed parse: comma scores, Points alias, Indies flag, Hardcore, Mode/Game Mode  
- Bot restart: save → load → standings identical  
- Dashboard / standings / announce stay inside Discord API size limits  

---

## What went right

1. **Rules engine is clean and unit-tested** — pure functions, no Discord deps; easy to trust for Season 1 points.  
2. **Best-of model survives chaos** — flooding 500–20k attempts never inflated a player past their true best verified score.  
3. **Closed-week path works** — lates stay pending until staff approve; staff `verified=True` path works while closed.  
4. **Idempotent message intake** — re-processing the same message id does not append a second row (critical when Discord retries or staff re-forwards).  
5. **State durability** — atomic write (`.tmp` → replace) + `.bak.json` + lock; concurrent writers finished with valid JSON.  
6. **Corrupt state does not crash the bot** — unreadable JSON → empty season shape + warning log.  
7. **Visual layer still green** — hero + versus render tests pass after logic work.  
8. **Performance headroom** — even at 15–17k submission rows, standings stay under ~250ms offline; real tourney volume will be far smaller.  
9. **Prove-live version string** — `2026-07-16-golive-v1` appears on help footer for deploy verification.  

---

## What went wrong (or almost did)

### Fixed this session (would have hurt in channel)

| Issue | Severity | What we did |
|-------|----------|-------------|
| **`/rs score set --week N` used to move `season.current_week`** | **High** | Staff fixing a week-1 score during week 2 would jump the live week. Fixed: `record_submission(..., week=)` + admin command no longer mutates current week. |
| **No message_id dedupe** | **Medium** | Same embed re-processed → many rows (best-of still OK, but state bloat + confusing history). Fixed: one message → one row. |
| **Standings/missing fields could exceed Discord 1024** | **Medium** | Large rosters / long team names could make `/rs standings update` or dashboard post **fail the API**. Fixed: `_pack_field_lines()` truncates with “+N more”. |
| **Disk writes under flood** | **Low–Med** | Every score called `save_state`; concurrent risk. Added `persist=` for tests + process lock on load/save. |
| **Playground burden false fail** | **Test-only** | Shared player ids polluted season totals. Isolated “Burden Lab” users. |

### Still open / not bugs but real risks

| Risk | Severity | Notes |
|------|----------|-------|
| **No live Discord smoke in this session** | **High (ops)** | Token, intents, slash sync, channel perms unproven until you run `python bot/main.py` in lab. |
| **Mode ≠ division still counts** | **Product** | By design with a warning. Wrong-mode spam can still land on the board; staff must watch. |
| **Score authenticity** | **Product** | Trust model is embed forward + staff. No anti-cheat beyond pending after close. |
| **Render free disk wipe** | **Ops** | JSON state on free tier can vanish; need backup discipline or persistent disk. |
| **Standings edit-in-place** | **Low** | Depends on bot message edit permissions; falls back to new post if edit fails. |
| **Rate limits on flood replies** | **Low** | Offline flood doesn’t hit Discord HTTP limits; a real channel stampede of replies/reactions could 429 (caught and swallowed). |
| **O(n) scan of all submissions** | **Low for S1** | Fine at tens of thousands; if multi-season archive grows huge, index later. |

### What testing could *not* prove offline

- Message Content Intent actually enabled  
- Slash commands appear (`/tourney`, `/rs`) after guild sync  
- Bot can see/send/pin in the lab channel  
- Real Smash Drums embed shape from Quest (parser tested with synthetic embeds)  
- Interaction 3s timeout under slow hero PNG render on weak hosts  
- Multi-bot conflict if SA / Indies bots share the channel  

---

## Issues found during audit (status)

| # | Finding | Status |
|---|---------|--------|
| 1 | Manual score moved current week | **Fixed** in `scores.py` + `commands_admin.py` |
| 2 | Message re-fire duplication | **Fixed** in `scores.py` |
| 3 | Embed 1024 overflow on big boards | **Fixed** in `dashboard.py` |
| 4 | State write locking | **Hardened** in `state.py` |
| 5 | Offline playground + go-live + extra stress harnesses | **Added** |
| 6 | Live channel E2E | **Blocked** on Discord app / env |

---

## Ideas that would help Season 1 (practical)

### Before / during open (high value)

1. **Lab channel weekend drill** — You + Laura + 2 alts: team add → song set → week open → real embeds → dashboard pin → week close → late → approve. Prove `BOT_VERSION` on `/tourney help`.  
2. **Staff runbook card** (pin privately): open checklist, close checklist, “how to approve late”, “how to fix wrong score without changing week”.  
3. **State backup ritual** — After team import and after each week close, download `data/rs_state.json` (or Render disk snapshot).  
4. **Strict mode optional** — Config flag `RS_REQUIRE_MODE_MATCH=1` to reject embeds when game mode ≠ team division (or force pending). Reduces wrong-division accidents.  
5. **Song title soft-check** — Warn (don’t block) if embed song doesn’t fuzzy-match featured song; catches “played wrong chart” early.  

### Mid-season quality of life

6. **`/rs team import` CSV** — Bulk register after Sesh closes (name, division, captain id, teammate id). Less slash fatigue.  
7. **`/rs submission list` public count** — “12 pending” so staff know backlog without digging.  
8. **Daily auto-dashboard refresh** — Optional job or staff habit: re-post/edit dashboard so “time left” and missing list stay fresh.  
9. **Captain-only confirm** — Optional reaction gate for disputed highs (staff still override).  
10. **Standings PNG** (P2 visuals) — Image board for mobile readability when many teams.  

### Resilience / scale

11. **Periodic JSON → SQLite** if free Render keeps eating state, or paid disk from day one of live.  
12. **Submission index by user+week** for O(1) best score if volume explodes.  
13. **Health check includes state age** — `/health` returns version + `updated_at` + team count for Render uptime monitors.  
14. **Rate-limit replies** — If >N scores/minute, react only (no reply embed) to avoid Discord 429 spam.  
15. **Audit log channel** — Mirror staff actions (week open/close, approve, score set) to a private mod log.  

### Player experience

16. **`/tourney my-score` shows pending** — “You have a late score waiting on staff.”  
17. **Public rules blurb** auto-posted on week open (already have announce; keep it short + song + deadline).  
18. **Division role pings** optional on announce (Classic / Fusion / Arcade roles).  

---

## Recommended lab smoke (when Discord is ready)

Copy from `CHECKLIST.md` section D; minimum path:

1. `pip install -r requirements.txt`  
2. Fill `.env` (`DISCORD_TOKEN`, `RS_GUILD_ID`, `RS_CHANNEL_ID`, `RS_ADMIN_ROLE_IDS`)  
3. `python bot/main.py` → log `RS TOURNEY BOT ONLINE BOT_VERSION=2026-07-16-golive-v1`  
4. `/tourney help` → version matches  
5. `/rs where` → channel/guild look right  
6. `/rs team add` ×2 → `/rs song set` → `/rs week open`  
7. Forward real Smash Drums score → ✅ + reply embed  
8. Forward same message again (or restart bot and re-handle) → no double count  
9. `/rs dashboard post` + pin  
10. `/rs week close` → forward score → ⏳ → `/rs submission approve`  
11. Restart bot → standings still correct  

---

## How to re-run all offline proof

```text
cd Desktop\RhythmSyndicateTourneyBot\bot
python test_rules.py
python test_deadline.py
python smoke_state.py
python test_golive.py
python test_extra_stress.py
python playground.py --teams 25 --flood 20000
python test_visuals.py
python test_verse.py
```

Expected: all exit 0, no FAIL lines.

---

## Verdict for “when it reaches the channel”

| Claim | Confidence |
|-------|------------|
| Scoring / standings / Burden won’t silently mis-rank under normal + chaotic load | **High** |
| Re-forwards and bot restarts won’t double-count the same message | **High** |
| Big rosters won’t crash standings/dashboard Discord posts on field size | **High** |
| Staff past-week score fix won’t jump the live week | **High** (fixed) |
| Zero drama on first real Discord process | **Medium** — env/intents/perms still unproven |
| Zero staff mistakes (wrong mode, wrong channel, forgotten close) | **Process** — needs lab drill + runbook |

**Ship posture:** Safe to take into a **private lab channel** as soon as Discord app + `.env` exist. Do **not** point at the public tourney channel until that lab drill is green and night-before env switch is planned.

---

## Session code changes (this go-live push)

- `bot/config.py` — `BOT_VERSION=2026-07-16-golive-v1`  
- `bot/scores.py` — `week=`, `persist=`, message_id dedupe  
- `bot/state.py` — lock on load/save  
- `bot/commands_admin.py` — score set uses `week=` without moving current week  
- `bot/dashboard.py` — field packing for Discord limits  
- `bot/playground.py` — offline season playground + flood  
- `bot/test_golive.py` — channel readiness suite  
- `bot/test_extra_stress.py` — expanded stress / edges  

---

*Report generated after full offline battery on Windows. Live Discord still the only missing gate.*
