from bot.database.connection import execute_query
from bot.database.backup import local_register_user
from bot.config.settings import DATABASE_URL


def register_user(user_id, username, first_name):
    local_register_user(user_id, username, first_name)
    if not DATABASE_URL:
        return False
    existing = execute_query(
        "SELECT user_id FROM bot_users WHERE user_id = %s",
        (user_id,), fetch_one=True,
    )
    if not existing:
        execute_query(
            "INSERT INTO bot_users (user_id, username, first_name) VALUES (%s, %s, %s)",
            (user_id, username, first_name),
        )
        return True
    return False


def is_user_banned(user_id):
    if not DATABASE_URL:
        return False
    result = execute_query(
        "SELECT is_banned FROM bot_users WHERE user_id = %s",
        (user_id,), fetch_one=True,
    )
    return result[0] if result else False


def set_ban_status(user_id, status):
    if not DATABASE_URL:
        return False
    result = execute_query(
        "UPDATE bot_users SET is_banned = %s WHERE user_id = %s",
        (status, user_id),
    )
    return result is not None and result > 0


def increment_gen_stat():
    if not DATABASE_URL:
        return
    execute_query("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_gens'")


def increment_bin_stat():
    if not DATABASE_URL:
        return
    execute_query("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_bin_lookups'")


def increment_request_stat():
    if not DATABASE_URL:
        return
    execute_query("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_requests'")


def increment_request_count(user_id):
    if not DATABASE_URL:
        return
    execute_query(
        "UPDATE bot_users SET request_count = request_count + 1 WHERE user_id = %s",
        (user_id,),
    )


def get_stats():
    if not DATABASE_URL:
        from bot.database.backup import get_local_user_count
        return get_local_user_count(), 0
    users = execute_query("SELECT COUNT(*) FROM bot_users", fetch_one=True)
    gens = execute_query(
        "SELECT value FROM bot_stats WHERE key = 'total_gens'", fetch_one=True,
    )
    return (users[0] if users else 0), (gens[0] if gens else 0)


def get_detailed_stats():
    from bot.database.backup import get_local_user_count
    local_count = get_local_user_count()
    if not DATABASE_URL:
        return local_count, local_count, 0, 0, 0, 0
    total = execute_query("SELECT COUNT(*) FROM bot_users", fetch_one=True)
    active = execute_query(
        "SELECT COUNT(*) FROM bot_users WHERE is_banned = FALSE", fetch_one=True,
    )
    banned = execute_query(
        "SELECT COUNT(*) FROM bot_users WHERE is_banned = TRUE", fetch_one=True,
    )
    gens = execute_query(
        "SELECT value FROM bot_stats WHERE key = 'total_gens'", fetch_one=True,
    )
    bin_lookups = execute_query(
        "SELECT value FROM bot_stats WHERE key = 'total_bin_lookups'", fetch_one=True,
    )
    requests = execute_query(
        "SELECT value FROM bot_stats WHERE key = 'total_requests'", fetch_one=True,
    )
    t = total[0] if total else 0
    return (
        max(t, local_count),
        active[0] if active else 0,
        banned[0] if banned else 0,
        gens[0] if gens else 0,
        bin_lookups[0] if bin_lookups else 0,
        requests[0] if requests else 0,
    )


def get_all_users():
    if not DATABASE_URL:
        from bot.database.backup import get_local_user_ids
        return get_local_user_ids()
    result = execute_query(
        "SELECT user_id FROM bot_users WHERE is_banned = FALSE", fetch=True,
    )
    return [row[0] for row in result] if result else []


def get_banned_users():
    if not DATABASE_URL:
        return []
    result = execute_query(
        "SELECT user_id, username, first_name FROM bot_users WHERE is_banned = TRUE",
        fetch=True,
    )
    return result if result else []


def get_recent_users(limit=10):
    if not DATABASE_URL:
        return []
    result = execute_query(
        "SELECT user_id, username, first_name, joined_at FROM bot_users ORDER BY joined_at DESC LIMIT %s",
        (limit,), fetch=True,
    )
    return result if result else []


def get_user_lang(user_id):
    if not DATABASE_URL:
        return "en"
    result = execute_query(
        "SELECT lang FROM bot_users WHERE user_id = %s",
        (user_id,), fetch_one=True,
    )
    return result[0] if result and result[0] else "en"


def set_user_lang(user_id, lang):
    if not DATABASE_URL:
        return
    execute_query(
        "UPDATE bot_users SET lang = %s WHERE user_id = %s",
        (lang, user_id),
    )
