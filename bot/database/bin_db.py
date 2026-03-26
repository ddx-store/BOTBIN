"""
BIN local cache — SQLite with WAL mode.

Schema: bin_data, bin_stats, request_log
Features:
  - Indexes on scheme / type / country_code / level for fast filtered queries
  - bulk_save_bins()  — single executemany for batch upserts (10-100x faster)
  - get_stale_bins()  — find BINs not refreshed in N days
  - get_full_stats()  — comprehensive DB analytics
  - Single-connection hit tracking (no nested connections)
"""

import sqlite3
import os
import time
from bot.utils.logger import get_logger

logger   = get_logger("bin_db")
DB_PATH  = os.path.join("data", "bin_cache.db")
os.makedirs("data", exist_ok=True)

_EXTRA_COLS = [
    ("bank_city",     "TEXT DEFAULT 'N/A'"),
    ("bank_url",      "TEXT DEFAULT 'N/A'"),
    ("bank_phone",    "TEXT DEFAULT 'N/A'"),
    ("currency",      "TEXT DEFAULT 'N/A'"),
    ("card_length",   "TEXT DEFAULT 'N/A'"),
    ("source",        "TEXT DEFAULT 'unknown'"),
    ("co_brand",      "TEXT DEFAULT 'N/A'"),
    ("contactless",   "INTEGER DEFAULT NULL"),
    ("issued_region", "TEXT DEFAULT 'N/A'"),
]


# ─── Connection factory ────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA cache_size=-8000")   # 8 MB page cache
    con.execute("PRAGMA temp_store=MEMORY")
    return con


# ─── Schema migration ─────────────────────────────────────────────────────────

def _migrate(con: sqlite3.Connection) -> None:
    existing = {row[1] for row in con.execute("PRAGMA table_info(bin_data)")}
    for col_name, col_def in _EXTRA_COLS:
        if col_name not in existing:
            con.execute(f"ALTER TABLE bin_data ADD COLUMN {col_name} {col_def}")
            logger.info(f"BIN DB migrated: added column '{col_name}'")


# ─── Initialization ────────────────────────────────────────────────────────────

def init_bin_db() -> None:
    try:
        with _conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS bin_data (
                    bin          TEXT PRIMARY KEY,
                    scheme       TEXT,
                    type         TEXT,
                    brand        TEXT,
                    level        TEXT,
                    bank         TEXT,
                    bank_city    TEXT DEFAULT 'N/A',
                    bank_url     TEXT DEFAULT 'N/A',
                    bank_phone   TEXT DEFAULT 'N/A',
                    country      TEXT,
                    country_code TEXT,
                    currency     TEXT DEFAULT 'N/A',
                    card_length  TEXT DEFAULT 'N/A',
                    emoji        TEXT,
                    prepaid      INTEGER,
                    source       TEXT DEFAULT 'unknown',
                    hit_count    INTEGER DEFAULT 0,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _migrate(con)

            # ── Indexes for fast filtered queries (get_random_bin, stale checks) ──
            con.execute("CREATE INDEX IF NOT EXISTS idx_bin_scheme       ON bin_data(scheme)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_bin_type         ON bin_data(type)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_bin_country_code ON bin_data(country_code)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_bin_level        ON bin_data(level)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_bin_updated_at   ON bin_data(updated_at)")

            con.execute("""
                CREATE TABLE IF NOT EXISTS bin_stats (
                    bin   TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS request_log (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action  TEXT,
                    detail  TEXT,
                    ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_rl_action ON request_log(action)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_rl_ts     ON request_log(ts)")

        logger.info("Local BIN DB initialized.")
    except Exception as e:
        logger.error(f"BIN DB init error: {e}")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return "\U0001f3f3\ufe0f"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _row_to_dict(row: sqlite3.Row) -> dict:
    cc = row["country_code"] or ""
    return {
        "scheme":       row["scheme"]       or "N/A",
        "type":         row["type"]         or "N/A",
        "brand":        row["brand"]        or "N/A",
        "level":        row["level"]        or "N/A",
        "bank":         row["bank"]         or "N/A",
        "bank_city":    row["bank_city"]    or "N/A",
        "bank_url":     row["bank_url"]     or "N/A",
        "bank_phone":   row["bank_phone"]   or "N/A",
        "country":      row["country"]      or "N/A",
        "country_code": cc                  or "N/A",
        "currency":     row["currency"]     or "N/A",
        "card_length":  row["card_length"]  or "N/A",
        "emoji":        _flag(cc),
        "prepaid":      bool(row["prepaid"]) if row["prepaid"] is not None else None,
        "source":       row["source"]       or "local",
    }


# ─── Core read/write ──────────────────────────────────────────────────────────

def get_bin_local(bin_number: str) -> dict | None:
    """
    Look up a BIN in local cache.
    Increments hit_count and bin_stats in a single connection — no nested opens.
    """
    key = bin_number[:6]
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM bin_data WHERE bin = ?", (key,)
            ).fetchone()
            if not row:
                return None

            # Single connection: update both hit_count and bin_stats atomically
            con.execute(
                "UPDATE bin_data SET hit_count = hit_count + 1 WHERE bin = ?", (key,)
            )
            con.execute("""
                INSERT INTO bin_stats (bin, count) VALUES (?, 1)
                ON CONFLICT(bin) DO UPDATE SET count = count + 1
            """, (key,))

            return _row_to_dict(row)
    except Exception as e:
        logger.error(f"BIN local lookup error: {e}")
    return None


def save_bin_local(bin_number: str, info: dict) -> None:
    """Single-BIN upsert (used by bin_lookup.py for on-demand caching)."""
    _do_upsert(_conn(), [(bin_number, info)])


def bulk_save_bins(items: list[tuple[str, dict]]) -> int:
    """
    Batch upsert: accepts list of (bin_number, info_dict) pairs.
    Returns number of rows written.
    Up to 100x faster than calling save_bin_local() in a loop.
    """
    if not items:
        return 0
    written = 0
    try:
        with _conn() as con:
            written = _do_upsert(con, items)
    except Exception as e:
        logger.error(f"bulk_save_bins error: {e}")
    return written


def _do_upsert(con: sqlite3.Connection, items: list[tuple[str, dict]]) -> int:
    """
    Internal helper: execute a batch upsert on an open connection.
    Returns count of rows processed.
    """
    def _prepaid(v):
        if v is True:  return 1
        if v is False: return 0
        return None

    rows = []
    for bin_number, info in items:
        rows.append((
            bin_number[:6],
            info.get("scheme",       "N/A"),
            info.get("type",         "N/A"),
            info.get("brand",        "N/A"),
            info.get("level",        "N/A"),
            info.get("bank",         "N/A"),
            info.get("bank_city",    "N/A"),
            info.get("bank_url",     "N/A"),
            info.get("bank_phone",   "N/A"),
            info.get("country",      "N/A"),
            info.get("country_code", "N/A"),
            info.get("currency",     "N/A"),
            info.get("card_length",  "N/A"),
            info.get("emoji",        "\U0001f3f3\ufe0f"),
            _prepaid(info.get("prepaid")),
            info.get("source",       "unknown"),
        ))

    con.executemany("""
        INSERT INTO bin_data
            (bin, scheme, type, brand, level, bank, bank_city, bank_url, bank_phone,
             country, country_code, currency, card_length, emoji, prepaid, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bin) DO UPDATE SET
            scheme=excluded.scheme, type=excluded.type, brand=excluded.brand,
            level=excluded.level, bank=excluded.bank, bank_city=excluded.bank_city,
            bank_url=excluded.bank_url, bank_phone=excluded.bank_phone,
            country=excluded.country, country_code=excluded.country_code,
            currency=excluded.currency, card_length=excluded.card_length,
            emoji=excluded.emoji, prepaid=excluded.prepaid,
            source=excluded.source, updated_at=CURRENT_TIMESTAMP
    """, rows)

    return len(rows)


# ─── Staleness management ─────────────────────────────────────────────────────

def get_stale_bins(older_than_days: int = 7, limit: int = 300) -> list[str]:
    """
    Return BIN numbers whose data is older than N days.
    Used by the updater's stale-refresh pass.
    """
    try:
        with _conn() as con:
            rows = con.execute("""
                SELECT bin FROM bin_data
                WHERE updated_at < datetime('now', ? || ' days')
                ORDER BY updated_at ASC
                LIMIT ?
            """, (f"-{older_than_days}", limit)).fetchall()
            return [r["bin"] for r in rows]
    except Exception as e:
        logger.error(f"get_stale_bins error: {e}")
    return []


def get_bins_by_filter(
    scheme: str = None,
    type_: str = None,
    country_code: str = None,
    limit: int = 50,
) -> list[dict]:
    """Return BINs matching optional filters — used by admin panel."""
    clauses, params = [], []
    if scheme:       clauses.append("UPPER(scheme) = ?");       params.append(scheme.upper())
    if type_:        clauses.append("UPPER(type) = ?");         params.append(type_.upper())
    if country_code: clauses.append("UPPER(country_code) = ?"); params.append(country_code.upper())

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    try:
        with _conn() as con:
            rows = con.execute(
                f"SELECT * FROM bin_data {where} ORDER BY hit_count DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_bins_by_filter error: {e}")
    return []


# ─── Stats & analytics ────────────────────────────────────────────────────────

def get_bin_db_size() -> int:
    try:
        with _conn() as con:
            row = con.execute("SELECT COUNT(*) FROM bin_data").fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def get_full_stats() -> dict:
    """Comprehensive DB analytics — used by admin panel."""
    try:
        with _conn() as con:
            total = con.execute("SELECT COUNT(*) FROM bin_data").fetchone()[0]

            scheme_rows = con.execute("""
                SELECT scheme, COUNT(*) as cnt FROM bin_data
                WHERE scheme != 'N/A'
                GROUP BY scheme ORDER BY cnt DESC LIMIT 10
            """).fetchall()

            country_rows = con.execute("""
                SELECT country_code, COUNT(*) as cnt FROM bin_data
                WHERE country_code != 'N/A'
                GROUP BY country_code ORDER BY cnt DESC LIMIT 10
            """).fetchall()

            stale_count = con.execute("""
                SELECT COUNT(*) FROM bin_data
                WHERE updated_at < datetime('now', '-7 days')
            """).fetchone()[0]

            fresh_count = con.execute("""
                SELECT COUNT(*) FROM bin_data
                WHERE updated_at >= datetime('now', '-1 day')
            """).fetchone()[0]

            top_bins_rows = con.execute("""
                SELECT b.bin, b.scheme, b.country_code, s.count
                FROM bin_stats s JOIN bin_data b ON b.bin = s.bin
                ORDER BY s.count DESC LIMIT 5
            """).fetchall()

            return {
                "total":        total,
                "stale_7d":     stale_count,
                "fresh_24h":    fresh_count,
                "by_scheme":    [(r["scheme"], r["cnt"]) for r in scheme_rows],
                "by_country":   [(r["country_code"], r["cnt"]) for r in country_rows],
                "top_bins":     [
                    {"bin": r["bin"], "scheme": r["scheme"],
                     "country": r["country_code"], "hits": r["count"]}
                    for r in top_bins_rows
                ],
            }
    except Exception as e:
        logger.error(f"get_full_stats error: {e}")
        return {"total": 0, "stale_7d": 0, "fresh_24h": 0,
                "by_scheme": [], "by_country": [], "top_bins": []}


def get_top_bins(limit: int = 5) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT bin, count FROM bin_stats ORDER BY count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["bin"], r["count"]) for r in rows]
    except Exception:
        return []


def track_bin_usage(bin_number: str) -> None:
    """Kept for backward-compat; get_bin_local now does this inline."""
    pass


# ─── Request log ──────────────────────────────────────────────────────────────

def log_request(user_id: int, action: str, detail: str = "") -> None:
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO request_log (user_id, action, detail) VALUES (?, ?, ?)",
                (user_id, action, detail[:200]),
            )
    except Exception:
        pass


def get_total_requests_today() -> int:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT COUNT(*) FROM request_log WHERE date(ts) = date('now')"
            ).fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def get_top_actions(limit: int = 5) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT action, COUNT(*) as cnt FROM request_log "
                "GROUP BY action ORDER BY cnt DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["action"], r["cnt"]) for r in rows]
    except Exception:
        return []


def get_user_summary(limit: int = 20) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT user_id, COUNT(*) as total FROM request_log "
                "GROUP BY user_id ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["user_id"], r["total"]) for r in rows]
    except Exception:
        return []


def get_recent_bin_lookups(limit: int = 15) -> list:
    try:
        with _conn() as con:
            rows = con.execute("""
                SELECT r.user_id, r.detail, r.ts,
                       b.scheme, b.type, b.bank, b.country, b.emoji
                FROM request_log r
                LEFT JOIN bin_data b ON b.bin = substr(r.detail, 1, 6)
                WHERE r.action IN ('bin', 'gen')
                ORDER BY r.ts DESC LIMIT ?
            """, (limit,)).fetchall()
            return [
                (r["user_id"], r["detail"], r["ts"],
                 r["scheme"], r["type"], r["bank"], r["country"], r["emoji"])
                for r in rows
            ]
    except Exception:
        return []
