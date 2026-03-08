import time
from bot.config.settings import RATE_LIMIT_MAX, RATE_LIMIT_WINDOW

_user_timestamps: dict = {}

BURST_WINDOW = 5
BURST_MAX = 5


def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    if user_id not in _user_timestamps:
        _user_timestamps[user_id] = []
    _user_timestamps[user_id] = [
        t for t in _user_timestamps[user_id] if now - t < RATE_LIMIT_WINDOW
    ]
    if len(_user_timestamps[user_id]) >= RATE_LIMIT_MAX:
        return False
    _user_timestamps[user_id].append(now)
    return True


def check_flood(user_id: int) -> bool:
    now = time.time()
    if user_id not in _user_timestamps:
        return False
    recent = [t for t in _user_timestamps[user_id] if now - t < BURST_WINDOW]
    return len(recent) >= BURST_MAX


def get_reset_in(user_id: int) -> int:
    if user_id not in _user_timestamps or not _user_timestamps[user_id]:
        return 0
    oldest = min(_user_timestamps[user_id])
    remaining = int(RATE_LIMIT_WINDOW - (time.time() - oldest))
    return max(0, remaining)
