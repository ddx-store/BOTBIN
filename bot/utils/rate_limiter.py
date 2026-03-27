import time
from bot.config.settings import RATE_LIMIT_MAX, RATE_LIMIT_WINDOW

_user_timestamps: dict = {}

BURST_WINDOW = 5
BURST_MAX = 5
_CLEANUP_EVERY = 3600
_last_cleanup = 0.0


def _cleanup_old_entries():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_EVERY:
        return
    _last_cleanup = now
    cutoff = now - RATE_LIMIT_WINDOW
    stale = [uid for uid, ts in _user_timestamps.items() if not ts or max(ts) < cutoff]
    for uid in stale:
        del _user_timestamps[uid]
    live_cutoff = now - LIVE_CHECK_WINDOW
    live_stale = [uid for uid, ts in _live_timestamps.items() if not ts or max(ts) < live_cutoff]
    for uid in live_stale:
        del _live_timestamps[uid]


def check_rate_limit(user_id: int) -> bool:
    _cleanup_old_entries()
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


LIVE_CHECK_WINDOW = 60
LIVE_CHECK_MAX = 5
_live_timestamps: dict = {}


def check_live_rate_limit(user_id: int) -> bool:
    now = time.time()
    if user_id not in _live_timestamps:
        _live_timestamps[user_id] = []
    _live_timestamps[user_id] = [
        t for t in _live_timestamps[user_id] if now - t < LIVE_CHECK_WINDOW
    ]
    if len(_live_timestamps[user_id]) >= LIVE_CHECK_MAX:
        return False
    _live_timestamps[user_id].append(now)
    return True


def get_reset_in(user_id: int) -> int:
    if user_id not in _user_timestamps or not _user_timestamps[user_id]:
        return 0
    oldest = min(_user_timestamps[user_id])
    remaining = int(RATE_LIMIT_WINDOW - (time.time() - oldest))
    return max(0, remaining)
