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
    execute_query(
        "UPDATE bot_users SET username = %s, first_name = %s WHERE user_id = %s",
        (username, first_name, user_id),
    )
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


def _local_increment(stat_key: str):
    from bot.database.backup import local_get_setting, local_set_setting
    cur = int(local_get_setting(stat_key) or 0)
    local_set_setting(stat_key, str(cur + 1))


def increment_gen_stat():
    _local_increment("stat_total_gens")
    if not DATABASE_URL:
        return
    execute_query("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_gens'")


def increment_bin_stat():
    _local_increment("stat_total_bin_lookups")
    if not DATABASE_URL:
        return
    execute_query("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_bin_lookups'")


def increment_request_stat():
    _local_increment("stat_total_requests")
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
        from bot.database.backup import local_get_setting
        gens = int(local_get_setting("stat_total_gens") or 0)
        bins = int(local_get_setting("stat_total_bin_lookups") or 0)
        reqs = int(local_get_setting("stat_total_requests") or 0)
        return local_count, local_count, 0, gens, bins, reqs
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


def get_user_info(user_id: int) -> dict | None:
    if DATABASE_URL:
        result = execute_query(
            """SELECT user_id, username, first_name, is_banned, is_premium,
                      premium_until, request_count, gen_count, joined_at,
                      COALESCE(chk_count, 0)
               FROM bot_users WHERE user_id = %s""",
            (user_id,), fetch_one=True,
        )
        if result:
            return {
                "user_id":       result[0],
                "username":      result[1],
                "first_name":    result[2],
                "is_banned":     result[3] or False,
                "is_premium":    result[4] or False,
                "premium_until": result[5],
                "request_count": result[6] or 0,
                "gen_count":     result[7] or 0,
                "joined_at":     result[8],
                "chk_count":     result[9] or 0,
            }
    from bot.database.backup import get_local_user_info
    return get_local_user_info(user_id)


def is_premium_user(user_id: int) -> bool:
    if not DATABASE_URL:
        return False
    result = execute_query(
        "SELECT is_premium, premium_until FROM bot_users WHERE user_id = %s",
        (user_id,), fetch_one=True,
    )
    if not result or not result[0]:
        return False
    if result[1]:
        from datetime import datetime
        if datetime.now() > result[1]:
            execute_query(
                "UPDATE bot_users SET is_premium = FALSE, premium_until = NULL WHERE user_id = %s",
                (user_id,),
            )
            return False
    return True


def set_premium(user_id: int, status: bool, days: int = None) -> bool:
    if not DATABASE_URL:
        return False
    if status and days:
        from datetime import datetime, timedelta
        until = datetime.now() + timedelta(days=days)
        result = execute_query(
            "UPDATE bot_users SET is_premium = TRUE, premium_until = %s WHERE user_id = %s",
            (until, user_id),
        )
    elif status:
        result = execute_query(
            "UPDATE bot_users SET is_premium = TRUE, premium_until = NULL WHERE user_id = %s",
            (user_id,),
        )
    else:
        result = execute_query(
            "UPDATE bot_users SET is_premium = FALSE, premium_until = NULL WHERE user_id = %s",
            (user_id,),
        )
    return result is not None and result > 0


def get_premium_users_count() -> int:
    if not DATABASE_URL:
        return 0
    result = execute_query(
        "SELECT COUNT(*) FROM bot_users WHERE is_premium = TRUE",
        fetch_one=True,
    )
    return result[0] if result else 0


def increment_gen_count(user_id: int):
    if not DATABASE_URL:
        return
    execute_query(
        "UPDATE bot_users SET gen_count = gen_count + 1 WHERE user_id = %s",
        (user_id,),
    )


def get_chk_count(user_id: int) -> int:
    if DATABASE_URL:
        result = execute_query(
            "SELECT chk_count FROM bot_users WHERE user_id = %s",
            (user_id,), fetch_one=True,
        )
        if result:
            return result[0] or 0
    from bot.database.backup import local_get_setting
    return int(local_get_setting(f"chk_count_{user_id}") or 0)


def increment_chk_count(user_id: int):
    from bot.database.backup import local_get_setting, local_set_setting
    cur = int(local_get_setting(f"chk_count_{user_id}") or 0)
    local_set_setting(f"chk_count_{user_id}", str(cur + 1))
    if DATABASE_URL:
        execute_query(
            "UPDATE bot_users SET chk_count = COALESCE(chk_count, 0) + 1 WHERE user_id = %s",
            (user_id,),
        )


def delete_user(user_id: int) -> bool:
    if not DATABASE_URL:
        return False
    result = execute_query(
        "DELETE FROM bot_users WHERE user_id = %s",
        (user_id,),
    )
    return result is not None and result > 0


def get_users_page(page: int = 0, per_page: int = 8):
    if not DATABASE_URL:
        return [], 0
    offset = page * per_page
    rows = execute_query(
        """SELECT user_id, username, first_name, is_banned, is_premium,
                  request_count, gen_count, joined_at
           FROM bot_users
           ORDER BY joined_at DESC
           LIMIT %s OFFSET %s""",
        (per_page, offset), fetch=True,
    ) or []
    total_row = execute_query("SELECT COUNT(*) FROM bot_users", fetch_one=True)
    total = total_row[0] if total_row else 0
    return rows, total


def search_user(query_str: str):
    if not DATABASE_URL:
        return None
    q = query_str.lstrip("@")
    if q.isdigit():
        result = execute_query(
            """SELECT user_id, username, first_name, is_banned, is_premium,
                      request_count, gen_count, joined_at
               FROM bot_users WHERE user_id = %s""",
            (int(q),), fetch_one=True,
        )
    else:
        result = execute_query(
            """SELECT user_id, username, first_name, is_banned, is_premium,
                      request_count, gen_count, joined_at
               FROM bot_users WHERE LOWER(username) = LOWER(%s)""",
            (q,), fetch_one=True,
        )
    if not result:
        return None
    return {
        "user_id":       result[0],
        "username":      result[1],
        "first_name":    result[2],
        "is_banned":     result[3] or False,
        "is_premium":    result[4] or False,
        "request_count": result[5] or 0,
        "gen_count":     result[6] or 0,
        "joined_at":     result[7],
    }


def get_setting(key: str) -> str | None:
    if DATABASE_URL:
        result = execute_query(
            "SELECT value FROM bot_settings WHERE key = %s",
            (key,), fetch_one=True,
        )
        if result:
            return result[0]
    from bot.database.backup import local_get_setting
    return local_get_setting(key)


def set_setting(key: str, value: str) -> bool:
    from bot.database.backup import local_set_setting
    local_set_setting(key, value)
    if not DATABASE_URL:
        return True
    result = execute_query(
        """INSERT INTO bot_settings (key, value, updated_at)
           VALUES (%s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP""",
        (key, value),
    )
    return result is not None


def delete_setting(key: str) -> bool:
    from bot.database.backup import local_delete_setting
    local_delete_setting(key)
    if not DATABASE_URL:
        return True
    result = execute_query(
        "DELETE FROM bot_settings WHERE key = %s",
        (key,),
    )
    return result is not None and result > 0


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
