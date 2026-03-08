import httpx
from bot.config.settings import BIN_LOOKUP_URL, BIN_LOOKUP_TIMEOUT
from bot.utils.cache import bin_cache
from bot.database.bin_db import get_bin_local, save_bin_local
from bot.utils.logger import get_logger

logger = get_logger("bin_lookup")

_EMPTY = {
    "scheme": "N/A",
    "type": "N/A",
    "brand": "N/A",
    "bank": "N/A",
    "country": "N/A",
    "country_code": "N/A",
    "emoji": "\U0001f3f3\ufe0f",
    "prepaid": None,
    "level": "N/A",
}


async def bin_lookup(bin_number: str) -> dict:
    key = bin_number[:6]

    cached = bin_cache.get(key)
    if cached:
        logger.info(f"BIN {key} → memory cache hit")
        return cached

    local = get_bin_local(key)
    if local:
        bin_cache.set(key, local)
        logger.info(f"BIN {key} → local DB hit")
        return local

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BIN_LOOKUP_URL}/{key}",
                headers={"Accept-Version": "3"},
                timeout=BIN_LOOKUP_TIMEOUT,
            )
        if resp.status_code == 200:
            data = resp.json()
            scheme = data.get("scheme", "N/A")
            brand = data.get("brand") or scheme
            result = {
                "scheme": scheme.upper() if scheme != "N/A" else "N/A",
                "type": (data.get("type") or "N/A").upper(),
                "brand": (brand or "N/A").upper(),
                "bank": (data.get("bank") or {}).get("name") or "N/A",
                "country": (data.get("country") or {}).get("name") or "N/A",
                "country_code": (data.get("country") or {}).get("alpha2") or "N/A",
                "emoji": (data.get("country") or {}).get("emoji") or "\U0001f3f3\ufe0f",
                "prepaid": data.get("prepaid"),
                "level": (brand or "N/A").upper(),
            }
            bin_cache.set(key, result)
            save_bin_local(key, result)
            logger.info(f"BIN {key} → fetched from API and saved")
            return result
        else:
            logger.warning(f"BIN {key} → API returned {resp.status_code}")
    except Exception as e:
        logger.error(f"BIN {key} → API error: {e}")

    return dict(_EMPTY)
