# Teams setup (Season 1 poster)

## What’s ready
- Poster roster scaffold: `data/roster_poster_season1.json`
- Name map for you to fill: `data/DISCORD_SMASH_NAME_MAP.csv`
- Apply helper: `python bot/apply_roster.py`

Week 1 = **raw scores only** (no captain bonus week).

## What I need from you
A list like:

| Discord name (server) | Smash Drums name (on score) | Team (poster) |
|----------------------|-----------------------------|-----------------|
| … | … | … |

Or fill the CSV columns: `discord_username`, `discord_id`, `smash_drums_name`.

**discord_id** = right‑click user in Discord (Developer Mode on) → Copy User ID.

## After you send the list
1. IDs go into the CSV / JSON  
2. Live bot: `/rs team import` **or** `/rs team add` for each team  
3. `/rs team list` → 8 teams  

## Poster teams (locked)

**Classic:** Buttmuncher & DPR · Daubo & Godspeeox · JS (JStill + Lara) · Kegen & Mikado  

**Arcade:** Minahh223 & D.M.G · Julz & Tammy  

**Fusion:** Victor · Sleepy (solo each)

## Until IDs land
Bot **cannot** score anyone — empty roster = no team match. Names alone are not enough.
