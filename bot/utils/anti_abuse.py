import time
from collections import defaultdict
from bot.utils.logger import get_logger

logger = get_logger("anti_abuse")

_violations: dict = defaultdict(list)
_bin_usage: dict  = {}

VIOLATION_WINDOW  = 600
MAX_VIOLATIONS    = 5
SAME_BIN_MAX      = 25
SAME_BIN_WINDOW   = 300


def record_violation(user_id: int, reason: str) -> bool:
    now = time.time()
    _violations[user_id] = [t for t in _violations[user_id] if now - t < VIOLATION_WINDOW]
    _violations[user_id].append(now)
    count = len(_violations[user_id])
    logger.warning(f"Violation #{count} | user={user_id} | reason={reason}")
    if count >= MAX_VIOLATIONS:
        from bot.database.queries import set_ban_status
        set_ban_status(user_id, True)
        _violations.pop(user_id, None)
        logger.warning(f"Auto-banned user {user_id} after {count} violations")
        return True
    return False


def check_bin_abuse(user_id: int, bin_prefix: str) -> bool:
    now  = time.time()
    key  = f"{user_id}:{bin_prefix[:6]}"
    entry = _bin_usage.get(key)
    if not entry or now - entry["first"] > SAME_BIN_WINDOW:
        _bin_usage[key] = {"count": 1, "first": now}
        return False
    entry["count"] += 1
    if entry["count"] > SAME_BIN_MAX:
        logger.warning(f"BIN abuse detected | user={user_id} | bin={bin_prefix[:6]} | count={entry['count']}")
        return True
    return False


def get_violation_count(user_id: int) -> int:
    now = time.time()
    _violations[user_id] = [t for t in _violations[user_id] if now - t < VIOLATION_WINDOW]
    return len(_violations[user_id])


def get_remaining_before_ban(user_id: int) -> int:
    return max(0, MAX_VIOLATIONS - get_violation_count(user_id))
