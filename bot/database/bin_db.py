import sqlite3
import os
from bot.utils.logger import get_logger

logger = get_logger("bin_db")

DB_PATH = os.path.join("data", "bin_cache.db")
os.makedirs("data", exist_ok=True)

_EXTRA_COLS = [
    ("bank_city",   "TEXT DEFAULT 'N/A'"),
    ("bank_url",    "TEXT DEFAULT 'N/A'"),
    ("bank_phone",  "TEXT DEFAULT 'N/A'"),
    ("currency",    "TEXT DEFAULT 'N/A'"),
    ("card_length", "TEXT DEFAULT 'N/A'"),
    ("source",      "TEXT DEFAULT 'unknown'"),
]


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _migrate(con):
    existing = {row[1] for row in con.execute("PRAGMA table_info(bin_data)")}
    for col_name, col_def in _EXTRA_COLS:
        if col_name not in existing:
            con.execute(f"ALTER TABLE bin_data ADD COLUMN {col_name} {col_def}")
            logger.info(f"BIN DB migrated: added column '{col_name}'")


def init_bin_db():
    try:
        with _conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS bin_data (
                    bin         TEXT PRIMARY KEY,
                    scheme      TEXT,
                    type        TEXT,
                    brand       TEXT,
                    level       TEXT,
                    bank        TEXT,
                    bank_city   TEXT DEFAULT 'N/A',
                    bank_url    TEXT DEFAULT 'N/A',
                    bank_phone  TEXT DEFAULT 'N/A',
                    country     TEXT,
                    country_code TEXT,
                    currency    TEXT DEFAULT 'N/A',
                    card_length TEXT DEFAULT 'N/A',
                    emoji       TEXT,
                    prepaid     INTEGER,
                    source      TEXT DEFAULT 'unknown',
                    hit_count   INTEGER DEFAULT 0,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _migrate(con)
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
        logger.info("Local BIN DB initialized.")
    except Exception as e:
        logger.error(f"BIN DB init error: {e}")


def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return "\U0001f3f3\ufe0f"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def get_bin_local(bin_number: str) -> dict | None:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM bin_data WHERE bin = ?",
                (bin_number[:6],),
            ).fetchone()
            if row:
                con.execute(
                    "UPDATE bin_data SET hit_count = hit_count + 1 WHERE bin = ?",
                    (bin_number[:6],),
                )
                track_bin_usage(bin_number[:6])
                cc = row["country_code"] or ""
                return {
                    "scheme":       row["scheme"]      or "N/A",
                    "type":         row["type"]        or "N/A",
                    "brand":        row["brand"]       or "N/A",
                    "level":        row["level"]       or "N/A",
                    "bank":         row["bank"]        or "N/A",
                    "bank_city":    row["bank_city"]   or "N/A",
                    "bank_url":     row["bank_url"]    or "N/A",
                    "bank_phone":   row["bank_phone"]  or "N/A",
                    "country":      row["country"]     or "N/A",
                    "country_code": cc                 or "N/A",
                    "currency":     row["currency"]    or "N/A",
                    "card_length":  row["card_length"] or "N/A",
                    "emoji":        _flag(cc),
                    "prepaid":      bool(row["prepaid"]) if row["prepaid"] is not None else None,
                    "source":       row["source"]      or "local",
                }
    except Exception as e:
        logger.error(f"BIN local lookup error: {e}")
    return None


def save_bin_local(bin_number: str, info: dict):
    try:
        prepaid_val = (
            1 if info.get("prepaid") is True
            else (0 if info.get("prepaid") is False else None)
        )
        with _conn() as con:
            con.execute("""
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
            """, (
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
                prepaid_val,
                info.get("source",       "unknown"),
            ))
    except Exception as e:
        logger.error(f"BIN save error: {e}")


def track_bin_usage(bin_number: str):
    try:
        with _conn() as con:
            con.execute("""
                INSERT INTO bin_stats (bin, count) VALUES (?, 1)
                ON CONFLICT(bin) DO UPDATE SET count = count + 1
            """, (bin_number[:6],))
    except Exception:
        pass


def log_request(user_id: int, action: str, detail: str = ""):
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO request_log (user_id, action, detail) VALUES (?, ?, ?)",
                (user_id, action, detail[:200]),
            )
    except Exception:
        pass


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


def get_bin_db_size() -> int:
    try:
        with _conn() as con:
            row = con.execute("SELECT COUNT(*) FROM bin_data").fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def get_total_requests_today() -> int:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT COUNT(*) FROM request_log WHERE date(ts) = date('now')",
            ).fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def get_top_actions(limit: int = 5) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT action, COUNT(*) as cnt FROM request_log GROUP BY action ORDER BY cnt DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["action"], r["cnt"]) for r in rows]
    except Exception:
        return []


def get_user_summary(limit: int = 20) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                """SELECT user_id, COUNT(*) as total
                   FROM request_log
                   GROUP BY user_id
                   ORDER BY total DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [(r["user_id"], r["total"]) for r in rows]
    except Exception:
        return []


def get_recent_bin_lookups(limit: int = 15) -> list:
    try:
        with _conn() as con:
            rows = con.execute(
                """SELECT r.user_id, r.detail, r.ts,
                          b.scheme, b.type, b.bank, b.country, b.emoji
                   FROM request_log r
                   LEFT JOIN bin_data b ON b.bin = substr(r.detail, 1, 6)
                   WHERE r.action IN ('bin', 'gen')
                   ORDER BY r.ts DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                (r["user_id"], r["detail"], r["ts"],
                 r["scheme"], r["type"], r["bank"], r["country"], r["emoji"])
                for r in rows
            ]
    except Exception:
        return []
