# Executor Status Bot

Discord bot that provides live Roblox executor status using the weao.xyz API, plus a server verification system.

## Features

- Prefix (`!`) and slash (`/`) commands
- Paginated executor list with Previous / Next buttons
- Platform info (Windows, Mac, Android, iOS)
- Detailed executor embeds with link buttons (Website / Discord / Purchase)
- Automatic background checker for version/status changes
- Server verification system with persistent button
- Custom help command

## Project Structure

```
discord-bot/
├── bot.py
├── commands/
│   ├── prefix/
│   │   ├── executors.py
│   │   ├── verification.py
│   │   └── help.py
│   └── slash/
│       ├── executors.py
│       ├── verification.py
│       └── help.py
├── utils/
│   ├── weao.py
│   └── pagination.py
├── data/
├── requirements.txt
├── .env.example
└── README.md
```

## Commands

### Executor
| Command | Description |
|---------|-------------|
| `!executors` / `/executors` | Paginated list of all executors |
| `!check <name>` / `/check` | Detailed status + link buttons |
| `!solara`, `!wave`, ... | Shortcuts for popular executors |

### Verification (Admin)
| Command | Description |
|---------|-------------|
| `!setupverify @Role [#logs]` / `/setupverify` | Configure verification |
| `!sendverify` / `/sendverify` | Send the verification panel |

### Utility
| Command | Description |
|---------|-------------|
| `!help` / `/help` | Show all commands |

## Verification Setup

1. Create a role (e.g. `Verified`)
2. Place the bot role **above** the verified role
3. Enable **Server Members Intent** in the Developer Portal
4. Run:
   ```
   !setupverify @Verified
   !sendverify
   ```

## Bot Setup

1. Create a bot at https://discord.com/developers/applications
2. Enable **Message Content Intent** and **Server Members Intent**
3. Invite with scopes `bot` + `applications.commands`

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.

```bash
python bot.py
```

## Notes

- Data source: weao.xyz (with domain fallback)
- Config and cache stored in `data/`
