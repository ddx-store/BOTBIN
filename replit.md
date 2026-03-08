# DDXSTORE Telegram Bot

A Telegram bot for card generation, BIN lookup, card checking, address generation, and fake identity generation. Instructions are in Arabic, all data responses are in English. Bot understands both Arabic and English input.

## Architecture

- **Type**: Backend-only Python Telegram bot (no frontend/web UI)
- **Language**: Python 3.12
- **Framework**: python-telegram-bot v21.0.1
- **Structure**: Modular (handlers, services, database, utils, config)
- **Language approach**: Instructions/errors in Arabic, data outputs in English. Input accepts both AR/EN.

## Project Structure

```
bot/
  config/
    settings.py          — Environment variables and constants
  database/
    connection.py        — PostgreSQL connection helper
    models.py            — Database schema initialization
    queries.py           — All database CRUD operations
    backup.py            — Local JSON backup system
    bin_db.py            — Local SQLite BIN cache DB + request logging
  handlers/
    start.py             — /start, /help commands (Arabic instructions)
    gen.py               — /gen card generation with queue support
    bin_cmd.py           — /bin BIN lookup
    check.py             — /chk card validation with Luhn + BIN info
    address.py           — /address random address
    fake.py              — /fake identity generator
    admin.py             — Admin panel, /ban, /unban, /broadcast, /stats
    router.py            — Smart message router (auto-detects BINs, card formats, gen patterns, country names)
  services/
    country_service.py   — Country detection (AR/EN), address generation, country info
    i18n.py              — Arabic instruction texts and error messages
  utils/
    luhn.py              — Luhn algorithm for card validation
    card_generator.py    — Card number generation logic
    bin_lookup.py        — BIN lookup: memory cache → local SQLite → external API
    rate_limiter.py      — Per-user rate limiting + flood/burst detection
    validators.py        — Input validation helpers
    cache.py             — TTL in-memory cache (1h BIN, 24h country)
    queue_manager.py     — Async request queue for large card generation (>50)
    logger.py            — Rotating file logger (logs/bot.log, 10MB × 5 files)
  app.py                 — Bot application builder and handler registration
main.py                  — Entry point
data/
  users.json             — Local user backup
  bin_cache.db           — SQLite local BIN database + request logs
logs/
  bot.log                — Application log (rotating)
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `DATABASE_URL` | Optional | PostgreSQL connection string |
| `ADMIN_ID` | Optional | Telegram user ID for admin access |

## Workflow

- **Start application**: `python main.py`

## Bot Commands

### User Commands
- `/start` — Welcome message (Arabic)
- `/help` — Full usage guide with box design (Arabic)
- `/gen <BIN> [month] [year] [count]` — Generate cards (default 10, max 200; >50 uses queue)
- `/bin <BIN>` — BIN information lookup (cached locally)
- `/chk <card>` — Check card validity (Luhn + BIN info)
- `/address <country>` — Random address (accepts Arabic/English country names)
- `/fake` — Complete fake identity (name/email/pass/DOB/SSN/phone/address/IP/UA)

### Admin Commands
- `/admin` — Admin panel with inline buttons
- `/stats` — Detailed statistics (users, gens, BIN lookups, top BINs, top actions, cache size)
- `/ban <user_id>` — Ban a user
- `/unban <user_id>` — Unban a user
- `/broadcast <message>` — Send message to all users

## Advanced Features

### Smart Input Detection (router.py)
- 6-8 digit BIN → Auto BIN lookup
- `453212xxxxxxxx` pattern → Auto card generation
- `453212|03|2027` or `453212-03-2027` → BIN lookup from card format
- Country name (AR/EN) → Country info

### Local BIN Database (data/bin_cache.db)
- SQLite: bin_data table stores all fetched BINs permanently
- Lookup order: memory cache → SQLite → external API
- Tracks per-BIN usage count for top-BIN stats

### Caching System
- Memory TTL cache: BIN info (1 hour), country (24 hours)
- Reduces external API calls significantly

### Request Queue
- Requests >50 cards use asyncio queue (max 3 pending per user)
- Progress indicator sent to user; result delivered when ready

### Flood Protection
- Burst detection: 5 requests in 5 seconds = flood warning
- Rate limit: 15 requests per 60 seconds

### Logging System
- Rotating file log: `logs/bot.log` (10MB × 5 backups)
- Console output with structured format
- Per-action request log in SQLite (user_id, action, detail, timestamp)

### Statistics (Admin)
- Total users, active, banned
- Total card generations, BIN lookups, requests
- Today's request count
- Top 5 most-used BINs
- Top 5 action types
- Cache size and local BIN DB size

## Database

### PostgreSQL (if DATABASE_URL set)
- `bot_users` — user_id, username, first_name, is_banned, request_count, joined_at, lang
- `bot_stats` — total_gens, total_bin_lookups, total_requests

### Local SQLite (data/bin_cache.db, always active)
- `bin_data` — BIN info cache with hit counts
- `bin_stats` — Per-BIN usage counts
- `request_log` — Per-request action log

Falls back to local `data/users.json` for user tracking when no PostgreSQL.

## Design Style
- Professional box design with ──────────────────── separators
- All data outputs in English with DDXSTORE branding and @ddx22 credit
- Generate Again inline buttons on: /gen, /address, /fake
