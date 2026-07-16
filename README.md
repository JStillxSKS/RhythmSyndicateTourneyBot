# Rhythm Syndicate Tournament Bot

Season 1 Discord bot for **Rhythm Syndicate** (Laura’s server).

- **Own bot** — not Surprise Attack, not Indies  
- Teams of 2 · Classic / Fusion / Arcade · 4 weeks  
- Players: `/tourney` · Staff: `/rs`  
- Foundation: teams, weeks, verified scores, Captain’s Burden, standings, dashboard  

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill DISCORD_TOKEN, RS_GUILD_ID, RS_CHANNEL_ID
python bot/main.py
```

See **SETUP.md** and **OPERATOR_GUIDE.md**.

## Tests

```bash
cd bot
python test_rules.py
```

## Version

Shown on `/tourney help` as `BOT_VERSION` in `bot/config.py`.
