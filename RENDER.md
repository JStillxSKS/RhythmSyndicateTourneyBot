# Deploy on Render

Same pattern as Surprise Attack: **Web Service** (free tier) + `/health` on `$PORT`.

## Service

- **Root:** repo root (`RhythmSyndicateTourneyBot`)  
- **Build:** `pip install -r requirements.txt`  
- **Start:** `python bot/main.py`  
- **Health:** `/health`  

Or use `render.yaml`.

## Env (dashboard secrets)

| Key | Required |
|-----|----------|
| `DISCORD_TOKEN` | yes |
| `RS_GUILD_ID` | recommended |
| `RS_CHANNEL_ID` | yes |
| `RS_SUBMIT_CHANNEL_ID` | optional |
| `RS_ADMIN_ROLE_IDS` | recommended |
| `PYTHON_VERSION` | `3.12.8` |

**Note:** Free web disks are ephemeral. State is JSON under `data/`. For production durability, use a persistent disk or external store later. For Season 1 testing, redeploy-aware backups of `data/rs_state.json` are wise.

## Prove live after deploy

1. Logs: `RS TOURNEY BOT ONLINE BOT_VERSION=…`  
2. Discord: `/tourney help` shows the same build string  
3. Staff: `/rs dashboard post` in the tourney channel  
