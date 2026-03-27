import time
from typing import Any, Optional


class TTLCache:
    def __init__(self, ttl: int = 3600):
        self._store: dict = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        ttl = ttl or self._ttl
        self._store[key] = (value, time.time() + ttl)

    def clear(self):
        self._store.clear()

    def size(self) -> int:
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if now < v[1]}
        return len(self._store)


bin_cache = TTLCache(ttl=3600)
country_cache = TTLCache(ttl=86400)
