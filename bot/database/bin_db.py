import sqlite3
import os
from bot.utils.logger import get_logger

logger = get_logger("bin_db")

DB_PATH = os.path.join("data", "bin_cache.db")
os.makedirs("data", exist_ok=True)


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_bin_db():
    try:
        with _conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS bin_data (
                    bin TEXT PRIMARY KEY,
                    scheme TEXT,
                    type TEXT,
                    brand TEXT,
                    bank TEXT,
                    country TEXT,
                    country_code TEXT,
                    emoji TEXT,
                    level TEXT,
                    prepaid INTEGER,
                    hit_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS bin_stats (
                    bin TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    detail TEXT,
                    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        logger.info("Local BIN DB initialized.")
    except Exception as e:
        logger.error(f"BIN DB init error: {e}")


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
                return {
                    "scheme": row["scheme"] or "N/A",
                    "type": row["type"] or "N/A",
                    "brand": row["brand"] or "N/A",
                    "bank": row["bank"] or "N/A",
                    "country": row["country"] or "N/A",
                    "country_code": row["country_code"] or "N/A",
                    "emoji": row["emoji"] or "\U0001f3f3\ufe0f",
                    "level": row["level"] or "N/A",
                    "prepaid": bool(row["prepaid"]) if row["prepaid"] is not None else None,
                }
    except Exception as e:
        logger.error(f"BIN local lookup error: {e}")
    return None


def save_bin_local(bin_number: str, info: dict):
    try:
        prepaid_val = 1 if info.get("prepaid") is True else (0 if info.get("prepaid") is False else None)
        with _conn() as con:
            con.execute("""
                INSERT INTO bin_data (bin, scheme, type, brand, bank, country, country_code, emoji, level, prepaid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bin) DO UPDATE SET
                    scheme=excluded.scheme, type=excluded.type, brand=excluded.brand,
                    bank=excluded.bank, country=excluded.country, country_code=excluded.country_code,
                    emoji=excluded.emoji, level=excluded.level, prepaid=excluded.prepaid,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                bin_number[:6],
                info.get("scheme", "N/A"), info.get("type", "N/A"), info.get("brand", "N/A"),
                info.get("bank", "N/A"), info.get("country", "N/A"), info.get("country_code", "N/A"),
                info.get("emoji", "\U0001f3f3\ufe0f"), info.get("level", "N/A"), prepaid_val,
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
