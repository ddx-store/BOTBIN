from bot.database.connection import get_connection
from bot.database.bin_db import init_bin_db
from bot.config.settings import DATABASE_URL
from bot.utils.logger import get_logger

logger = get_logger("models")


def init_db():
    init_bin_db()

    if not DATABASE_URL:
        logger.info("No DATABASE_URL — using local storage only.")
        return

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                request_count BIGINT DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                key TEXT PRIMARY KEY,
                value BIGINT DEFAULT 0
            )
        """)

        for key in ("total_gens", "total_bin_lookups", "total_requests"):
            cur.execute(
                "INSERT INTO bot_stats (key, value) VALUES (%s, 0) ON CONFLICT DO NOTHING",
                (key,),
            )

        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='is_banned'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='request_count'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN request_count BIGINT DEFAULT 0;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='lang'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN lang TEXT DEFAULT 'en';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='is_premium'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN is_premium BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='premium_until'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN premium_until TIMESTAMP DEFAULT NULL;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='bot_users' AND column_name='gen_count'
                ) THEN
                    ALTER TABLE bot_users ADD COLUMN gen_count BIGINT DEFAULT 0;
                END IF;
            END $$;
        """)

        conn.commit()
        cur.close()
        logger.info("PostgreSQL DB initialized.")
    except Exception as e:
        logger.error(f"DB Init Error: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
