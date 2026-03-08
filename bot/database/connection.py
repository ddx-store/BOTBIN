import psycopg2
from bot.config.settings import DATABASE_URL


def get_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)


def execute_query(query, params=None, fetch=False, fetch_one=False):
    if not DATABASE_URL:
        return None
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch:
            result = cur.fetchall()
        else:
            result = cur.rowcount
        conn.commit()
        cur.close()
        return result
    except Exception as e:
        print(f"DB Error: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
