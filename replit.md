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
│   └── utils/             # logger, rate_limiter, cache, formatter, bin_lookup, crypto, stripe_checker
```

## Architecture

- **Runtime**: Python 3.12
- **Framework**: python-telegram-bot 21.0.1
- **Database**: PostgreSQL (users/stats: user_id, username, first_name, is_banned, is_premium, premium_until, request_count, gen_count, joined_at, lang) + SQLite (BIN cache, WAL+indexes)
- **BIN Sources**: binlist.net → handyapi.com → range_detect (memory cache → SQLite → API)
- **BIN Update**: Manual-only via `/updatebins`
- **Countries**: 51 countries across 6 regions (CITY_DATA) with cities/districts/streets/zip/phone
- **SEED_BINS**: 696 unique BINs covering Gulf/MENA, Europe, Asia, LatAm, Africa
- **Membership**: Free (10 cards/gen) vs Premium (200 cards/gen); admin grants via /premium

## User Commands

| Command | Description |
|---|---|
| `/gen BIN\|MM\|YY[\|CVV][ count]` | Generate cards (all separator formats supported) |
| `/bin <6-digit BIN>` | BIN lookup with scheme/type/level/bank/country/region |
| `/chk <card>[\|MM\|YY[\|CVV]]` | Card validation (Luhn + expiry + length + BIN region + live Stripe check if key set) |
| `/address <country>` | Random address with district field |
| `/fake <country>` | Fake identity |
| `/myinfo` | Show user's own stats (join date, request count, gen count, premium status) |

## Admin Commands

| Command | Description |
|---|---|
| `/admin` | Admin panel (stats, users, BIN log, premium list) |
| `/ban <id>` / `/unban <id>` | Ban/unban user |
| `/premium <id> [days]` | Grant premium (permanent or N days) |
| `/unpremium <id>` | Revoke premium |
| `/broadcast <msg>` | Message all users |
| `/setkey sk_live_...` | Set Stripe live key (encrypted in DB) |
| `/removekey` | Remove stored Stripe key |
| `/updatebins` | Refresh BIN cache |

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

## Security Hardening (Applied)

- **HTML injection protection**: All user-controlled fields (username, first_name, forwarded text) escaped via `html.escape()` before embedding in HTML-mode Telegram messages (admin.py, router.py)
- **Admin self-ban protection**: `/ban` command and panel callback both block banning the admin's own ID
- **File descriptor leak fix**: Backup file opened with `with` context manager
- **Username sync**: `register_user` now updates username/first_name on every `/start` (existing users get updated, return value preserved for new/returning distinction)
- **parse_mode consistency**: `router.py` address auto-detect now sends `parse_mode="HTML"` matching `<code>` tags in `get_address_text`

## Live Card Check (Stripe Integration)

- **Admin key management**: `/setkey` encrypts Stripe key with Fernet (SHA256 of BOT_TOKEN) and stores in `bot_settings` table; `/removekey` deletes it
- **Live check flow**: When card has number+month+year+cvv and Luhn/length/expiry pass, and a Stripe key is stored, creates PaymentMethod → PaymentIntent ($1 USD) → auto-refund if succeeded
- **Safety**: Refund failure is treated as hard error (never reports "live" without confirmed refund); 3D Secure detected; 20+ decline code mappings
- **Rate limit**: Separate 5/min per-user limit for live checks (in-memory, cleaned hourly)
- **Security**: Key never echoed in plain text (masked `sk_live_...xxxx`); stored encrypted in PostgreSQL `bot_settings` table
- **Dependencies**: `cryptography==44.0.0` added for Fernet encryption

## Workflow

- **Start application**: `python main.py` (console output)
