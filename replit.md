# DDXSTORE Telegram Bot

## Overview

A Telegram bot (Python) for DDXSTORE that:
- Fetches verification codes from Gmail automatically
- Manages users (ban/unban, broadcast messages)
- Card generation and BIN lookup tools
- Address and fake data generation
- Admin panel with stats and user management
- PostgreSQL-backed user and stats storage
- Automatic backup system

## Project Structure

```
telegram-bot/
├── main.py               # Entry point
├── requirements.txt      # Python dependencies
├── Procfile              # Railway deploy config
├── bot/
│   ├── app.py            # Application setup and handler registration
│   ├── config/
│   │   └── settings.py   # Environment-based configuration
│   ├── database/
│   │   ├── connection.py  # PostgreSQL connection helper
│   │   ├── models.py      # DB schema initialization
│   │   ├── queries.py     # DB queries
│   │   ├── bin_db.py      # BIN database helpers
│   │   └── backup.py      # Backup system
│   ├── handlers/          # Telegram command handlers
│   │   ├── admin.py       # Admin panel + BIN update commands
│   │   ├── bin_cmd.py     # /bin lookup
│   │   ├── check.py       # /chk card checker
│   │   ├── address.py     # /address generator
│   │   ├── fake.py        # /fake identity
│   │   └── gen.py         # /gen card generator
│   ├── services/
│   │   ├── country_service.py   # Country/address data
│   │   ├── i18n.py              # Message strings
│   │   └── bin_updater/         # BIN update engine
│   │       ├── sources.py       # 3 API sources (binlist/handyapi/freebinlist)
│   │       ├── updater.py       # BinListUpdater class + get_random_bin()
│   │       └── scheduler.py     # 24h background scheduler
│   └── utils/             # logger, rate_limiter, cache, formatter, bin_lookup
```

## Architecture

- **Runtime**: Python 3.12
- **Framework**: python-telegram-bot 21.0.1
- **Database**: PostgreSQL (users/stats) + SQLite (BIN cache, 6+ new columns)
- **BIN Sources**: binlist.net → handyapi.com → freebinlist.net → range detection
- **Auto-Update**: BIN DB refreshes every 24h in background (starts 90s after boot)

## Required Environment Secrets

- `BOT_TOKEN` - Telegram bot token from @BotFather
- `ADMIN_ID` - Telegram user ID of the admin
- `GMAIL_USER` - Gmail address for fetching verification codes
- `GMAIL_APP_PASSWORD` - Gmail App Password
- `GMAIL_LABEL` - Gmail label to read from (default: TO_BOT)
- `GIFT_CHANNEL_ID` - Telegram channel ID for gifts
- `SUPPORT_WHATSAPP_URL` - WhatsApp support link

## Running

The bot runs as a background worker via polling (no web server needed).

```bash
python main.py
```

## Workflow

- **Start application**: `python main.py` (console output)
