# Rhythm Syndicate Tournament Bot — Setup

Own Discord bot for Laura’s **Rhythm Syndicate** Season 1 (not Surprise Attack).

**Full Discord checklist PDF:** `DISCORD_SETUP.pdf` (also on Desktop as  
`Rhythm_Syndicate_Tourney_Bot_Discord_Setup.pdf`).

## 1. Discord application

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application  
2. **Bot** → Add Bot → copy token → `DISCORD_TOKEN`  
3. Enable **Message Content Intent** (score embed reads)  
4. OAuth2 → URL Generator: scopes `bot` + `applications.commands`  
5. Permissions: View Channel, Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions  
6. Invite to the Syndicate server (or a test server first)  

## 2. Local env

```text
copy .env.example .env
```

Fill in:

| Variable | Meaning |
|----------|---------|
| `DISCORD_TOKEN` | Bot token |
| `RS_GUILD_ID` | Server ID (faster slash sync) |
| `RS_CHANNEL_ID` | Tourney channel (dashboard + scores) |
| `RS_ADMIN_ROLE_IDS` | Comma-separated staff role IDs |

```text
pip install -r requirements.txt
python bot/main.py
```

Prove live: `/tourney help` shows `BOT_VERSION`.

## 3. First-run staff flow

1. `/rs team add` for each team (captain + teammate + division)  
2. `/rs song set title:...`  
3. `/rs week open`  
4. `/rs dashboard post`  
5. Players forward Smash Drums **score embeds** in the tourney channel  
6. `/rs week close` at deadline; late → `/rs submission approve`  
7. `/rs standings update` as needed  

## 4. Render

See `RENDER.md`.
